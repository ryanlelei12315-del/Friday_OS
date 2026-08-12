import logging
import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Union

from core.runtime_state import TaskState, PlanStep, StepStatus
from core.tool_contract import ToolResult, ToolStatus, ToolRiskLevel
from core.tool_registry import ToolRegistry, FridayBaseTool
from core.policy_engine import PolicyEngine, PolicyDecision

logger = logging.getLogger("FridayOrchestrator")


class FridayOrchestrator:
    def __init__(
        self,
        tool_registry: Union[ToolRegistry, Dict[str, Callable]],
        policy_engine: Optional[PolicyEngine] = None,
        verification_registry: Optional[Dict[str, Callable]] = None,
    ):
        """
        Friday Core Orchestrator implementing a stateful control loop:
        OBSERVE -> PLAN -> EXECUTE -> VERIFY -> REFLECT -> COMPLETE

        Supports Phase 1 Dict registries and Phase 2 typed ToolRegistry + PolicyEngine.
        """
        self.registry = tool_registry
        self.policy = policy_engine or PolicyEngine()
        self.verifiers = verification_registry or {}

        # Is this running under strict Phase 2 ToolRegistry mode?
        self.strict_phase2 = isinstance(tool_registry, ToolRegistry)

    async def run_task(
        self,
        state: TaskState,
        plan_generator: Callable[[str], asyncio.Future],
        observe_context_callback: Optional[Callable[[], Dict[str, Any]]] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> TaskState:
        """
        Main execution loop representing our state machine.
        Continues executing until the plan is complete or enters a terminal failed state.
        """
        logger.info(f"[Orchestrator] COMMENCING GOAL: '{state.goal}'")
        self._emit_event(event_callback, "AgentStarted", {"task_id": state.task_id, "goal": state.goal})

        current_state = "OBSERVE"

        while current_state != "COMPLETE" and current_state != "FAILED":
            logger.info(f"[Orchestrator] TRANSITION -> State: {current_state}")

            if current_state == "OBSERVE":
                # 1. Gather active OS context to inject or evaluate constraints
                if observe_context_callback:
                    try:
                        context = observe_context_callback()
                        state.metadata["observed_context"] = context
                        logger.info(f"[Observe] Context captured: {context}")
                    except Exception as e:
                        logger.error(f"[Observe] Context capture failed: {e}")

                current_state = "PLAN"

            elif current_state == "PLAN":
                # 2. Decompose or adapt the plan based on progress
                if not state.plan:
                    logger.info("[Plan] Generating initial structured plan steps...")
                    try:
                        plan_steps = await plan_generator(state.goal)
                        state.plan = plan_steps
                        logger.info(f"[Plan] Created plan with {len(state.plan)} steps.")
                    except Exception as e:
                        logger.error(f"[Plan] Generation failed: {e}")
                        state.final_result = f"Planning failed: {str(e)}"
                        current_state = "FAILED"
                        self._emit_event(event_callback, "PlanGenerationFailed", {"task_id": state.task_id, "error": str(e)})
                        continue
                else:
                    logger.info("[Plan] Re-evaluating existing plan steps.")

                current_state = "EXECUTE"

            elif current_state == "EXECUTE":
                # 3. Find current queued/failed step and execute its mapped tool
                step = self._get_current_step(state)
                if not step:
                    logger.info("[Execute] No remaining queued steps. Transitioning to REFLECT.")
                    current_state = "REFLECT"
                    continue

                logger.info(f"[Execute] Running step {step.step_id}: '{step.description}'")
                step.status = StepStatus.RUNNING

                # Retrieve tool name
                tool_name = step.tool_name

                # ----------------------------------------------------
                # PATH A: Phase 2 Typed ToolRegistry Control Loop
                # ----------------------------------------------------
                if self.strict_phase2:
                    tool = self.registry.get(tool_name)
                    if not tool:
                        err_msg = f"Tool '{tool_name}' not registered in Friday Core."
                        logger.error(f"[Execute] {err_msg}")
                        step.status = StepStatus.FAILED
                        step.error = err_msg
                        self._emit_event(event_callback, "ToolCallFailed", {"task_id": state.task_id, "step_id": step.step_id, "tool_name": tool_name, "error_category": "NOT_AVAILABLE", "error": err_msg})
                        current_state = "VERIFY"
                        continue

                    # 3.1 Policy Engine Checks
                    self._emit_event(event_callback, "ToolPolicyEvaluationStarted", {"task_id": state.task_id, "tool_name": tool_name})
                    decision, policy_reason = self.policy.evaluate(tool.contract)

                    if decision == PolicyDecision.DENY:
                        err_msg = f"Security Policy Blocked tool execution: {policy_reason}"
                        logger.error(f"[Execute] {err_msg}")
                        step.status = StepStatus.FAILED
                        step.error = err_msg
                        self._emit_event(event_callback, "ToolCallDenied", {"task_id": state.task_id, "step_id": step.step_id, "tool_name": tool_name, "error_category": "DENIED", "reason": policy_reason})
                        current_state = "VERIFY"
                        continue

                    elif decision == PolicyDecision.REQUIRES_APPROVAL:
                        # Request user validation approval
                        self._emit_event(event_callback, "ToolApprovalRequested", {"task_id": state.task_id, "step_id": step.step_id, "tool_name": tool_name, "risk_level": tool.contract.risk_level.value})

                        # In strict testing/headless context, check task approval state
                        if state.approval_state == "rejected":
                            err_msg = f"User rejected approval for execution of {tool_name}."
                            logger.warning(f"[Execute] {err_msg}")
                            step.status = StepStatus.FAILED
                            step.error = err_msg
                            self._emit_event(event_callback, "ToolCallDenied", {"task_id": state.task_id, "step_id": step.step_id, "tool_name": tool_name, "error_category": "DENIED", "reason": "User rejected approval"})
                            current_state = "VERIFY"
                            continue
                        else:
                            logger.info(f"[Execute] Tool approval granted (or defaulted) for {tool_name}.")
                            state.approval_state = "approved"

                    # 3.2 Input Schema Validation
                    try:
                        tool.validate_args(step.tool_args)
                    except ValueError as e:
                        err_msg = f"Validation failed: {str(e)}"
                        logger.error(f"[Execute] {err_msg}")
                        step.status = StepStatus.FAILED
                        step.error = err_msg
                        self._emit_event(event_callback, "ToolCallFailed", {"task_id": state.task_id, "step_id": step.step_id, "tool_name": tool_name, "error_category": "INVALID_INPUT", "error": err_msg})
                        current_state = "VERIFY"
                        continue

                    # 3.3 Execute under explicit timeout limits
                    start_time = time.time()
                    self._emit_event(event_callback, "ToolCallStarted", {"task_id": state.task_id, "step_id": step.step_id, "tool_name": tool_name})
                    try:
                        # Run the typed tool base execution
                        result: ToolResult = await asyncio.wait_for(
                            tool.run(**step.tool_args), timeout=tool.contract.timeout
                        )
                        duration = time.time() - start_time

                        # Update TaskState from structured result observations
                        step.observation = result.observation
                        if result.status == ToolStatus.SUCCESS:
                            step.status = StepStatus.SUCCESS
                            self._emit_event(event_callback, "ToolCallCompleted", {"task_id": state.task_id, "step_id": step.step_id, "tool_name": tool_name, "duration": duration, "result_status": "SUCCESS"})
                        else:
                            step.status = StepStatus.FAILED
                            step.error = result.error
                            self._emit_event(event_callback, "ToolCallFailed", {"task_id": state.task_id, "step_id": step.step_id, "tool_name": tool_name, "duration": duration, "error_category": result.status.value, "error": result.error})
                    except asyncio.TimeoutError:
                        duration = time.time() - start_time
                        logger.error(f"[Execute] Tool execution timed out after {tool.contract.timeout}s.")
                        step.status = StepStatus.FAILED
                        step.error = f"Timeout exceeded ({tool.contract.timeout}s)."
                        self._emit_event(event_callback, "ToolCallFailed", {"task_id": state.task_id, "step_id": step.step_id, "tool_name": tool_name, "duration": duration, "error_category": "TIMEOUT", "error": "Execution exceeded timeout envelope"})
                    except Exception as e:
                        duration = time.time() - start_time
                        logger.error(f"[Execute] Tool crashed: {e}")
                        step.status = StepStatus.FAILED
                        step.error = str(e)
                        self._emit_event(event_callback, "ToolCallFailed", {"task_id": state.task_id, "step_id": step.step_id, "tool_name": tool_name, "duration": duration, "error_category": "FAILED", "error": str(e)})

                    current_state = "VERIFY"

                # ----------------------------------------------------
                # PATH B: Legacy Phase 1 Dictionary Control Loop
                # ----------------------------------------------------
                else:
                    if not tool_name or tool_name not in self.registry:
                        err_msg = f"Tool '{tool_name}' not found in registry."
                        logger.error(f"[Execute] {err_msg}")
                        step.status = StepStatus.FAILED
                        step.error = err_msg
                        current_state = "VERIFY"
                        continue

                    try:
                        tool_func = self.registry[tool_name]
                        logger.info(f"[Execute] Invoking tool '{tool_name}' with args {step.tool_args}")

                        result = await asyncio.wait_for(
                            tool_func(**step.tool_args), timeout=30.0
                        )
                        step.observation = str(result)
                        logger.info(f"[Execute] Tool returned outcome: {result}")
                    except asyncio.TimeoutError:
                        logger.error(f"[Execute] Tool run exceeded execution timeout limit.")
                        step.status = StepStatus.FAILED
                        step.error = "Timeout exceeded."
                    except Exception as e:
                        logger.error(f"[Execute] Tool crashed: {e}")
                        step.status = StepStatus.FAILED
                        step.error = str(e)

                    current_state = "VERIFY"

            elif current_state == "VERIFY":
                # 4. Perform deterministic verification checks to assert outcome
                step = self._get_active_or_last_step(state)
                if not step:
                    current_state = "EXECUTE"
                    continue

                logger.info(f"[Verify] Asserting execution outcome of step {step.step_id}...")

                verification_success = True
                verifier_name = step.verification_check

                # Check if a custom verifier callback is registered
                if verifier_name and verifier_name in self.verifiers:
                    try:
                        verifier = self.verifiers[verifier_name]
                        logger.info(f"[Verify] Invoking custom state verifier '{verifier_name}'")
                        verification_success = await verifier(step)
                        logger.info(f"[Verify] Verifier outcome: {verification_success}")
                    except Exception as e:
                        logger.error(f"[Verify] Custom state verifier crashed: {e}")
                        verification_success = False
                else:
                    # Default fallback: check if tool ran successfully
                    verification_success = step.status != StepStatus.FAILED

                if verification_success:
                    step.status = StepStatus.SUCCESS
                    state.current_step_id = step.step_id + 1
                    logger.info(f"[Verify] Step {step.step_id} verified successfully!")
                    current_state = "EXECUTE"
                else:
                    step.status = StepStatus.FAILED
                    logger.warning(f"[Verify] Step {step.step_id} verification failed.")

                    # 5. Self-Healing check
                    current_state = await self._handle_self_healing(state, step)

            elif current_state == "REFLECT":
                # 6. Analyze plan compliance and format conversational summaries
                all_success = all(s.status == StepStatus.SUCCESS for s in state.plan)
                if all_success:
                    state.final_result = "Goal completed successfully, sir."
                    logger.info("[Reflect] All plan steps completed. Goal satisfied.")
                    current_state = "COMPLETE"
                    self._emit_event(event_callback, "TaskCompleted", {"task_id": state.task_id, "final_result": state.final_result})
                else:
                    state.final_result = "Plan execution halted due to failures."
                    logger.warning("[Reflect] Some plan steps remain in failed state.")
                    current_state = "FAILED"
                    self._emit_event(event_callback, "TaskFailed", {"task_id": state.task_id, "final_result": state.final_result})

        logger.info(f"[Orchestrator] GOAL EXECUTION FINISHED. Status: {current_state}")
        return state

    def _get_current_step(self, state: TaskState) -> Optional[PlanStep]:
        for step in state.plan:
            if step.status in [StepStatus.QUEUED, StepStatus.FAILED]:
                return step
        return None

    def _get_active_or_last_step(self, state: TaskState) -> Optional[PlanStep]:
        for step in reversed(state.plan):
            if step.status in [StepStatus.RUNNING, StepStatus.FAILED, StepStatus.SUCCESS]:
                return step
        return None

    async def _handle_self_healing(self, state: TaskState, step: PlanStep) -> str:
        """
        Features self-healing: Retries step with altered parameters, or falls back to
        escalating the problem to the user when retries are exhausted.
        """
        current_retries = state.retry_counts.get(step.step_id, 0)

        if current_retries < state.max_retries_per_step:
            state.retry_counts[step.step_id] = current_retries + 1
            logger.warning(
                f"[Self-Healing] Retry attempt {current_retries + 1}/{state.max_retries_per_step} for step {step.step_id}."
            )

            await asyncio.sleep(0.1 * (current_retries + 1))  # Fast backoff delay for testing

            step.status = StepStatus.QUEUED  # Reset to allow re-execution
            return "EXECUTE"
        else:
            logger.error(f"[Self-Healing] Step {step.step_id} exceeded maximum retry envelope. Escalating to human, sir.")
            step.status = StepStatus.FAILED
            state.final_result = f"Step {step.step_id} failed permanently: {step.error or 'Verification check failed'}"
            return "FAILED"

    def _emit_event(self, callback: Optional[Callable[[str, Dict[str, Any]], None]], event_name: str, payload: Dict[str, Any]):
        if callback:
            try:
                payload["timestamp"] = time.time()
                callback(event_name, payload)
            except Exception as e:
                logger.error(f"[Event] Failed to emit structured event '{event_name}': {e}")
