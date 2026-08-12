import logging
import asyncio
from typing import Any, Callable, Dict, List, Optional
from core.runtime_state import TaskState, PlanStep, StepStatus

logger = logging.getLogger("FridayOrchestrator")


class FridayOrchestrator:
    def __init__(
        self,
        tool_registry: Dict[str, Callable],
        verification_registry: Optional[Dict[str, Callable]] = None,
    ):
        """
        Friday Core Orchestrator implementing a stateful control loop:
        OBSERVE -> PLAN -> EXECUTE -> VERIFY -> REFLECT -> COMPLETE

        Args:
            tool_registry: Dict mapping tool names to executable functions.
            verification_registry: Optional dict mapping verification check names to state verifier functions.
        """
        self.tools = tool_registry
        self.verifiers = verification_registry or {}

    async def run_task(
        self,
        state: TaskState,
        plan_generator: Callable[[str], asyncio.Future],
        observe_context_callback: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> TaskState:
        """
        Main execution loop representing our state machine.
        Continues executing until the plan is complete or enters a terminal failed state.
        """
        logger.info(f"[Orchestrator] COMMENCING GOAL: '{state.goal}'")

        # Initial loop state
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
                        continue
                else:
                    logger.info("[Plan] Re-evaluating existing plan steps.")

                # Move to executing the first queued step
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

                # Retrieve tool
                tool_name = step.tool_name
                if not tool_name or tool_name not in self.tools:
                    err_msg = f"Tool '{tool_name}' not found in registry."
                    logger.error(f"[Execute] {err_msg}")
                    step.status = StepStatus.FAILED
                    step.error = err_msg
                    current_state = "VERIFY"
                    continue

                # Run tool asynchronously with safety timeout checks
                try:
                    tool_func = self.tools[tool_name]
                    logger.info(f"[Execute] Invoking tool '{tool_name}' with args {step.tool_args}")

                    # Tool executes under standard timeout envelope (e.g. 30 seconds)
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
                    # Default: fallback to verifying tool execution didn't throw an error
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
                else:
                    state.final_result = "Plan execution halted due to failures."
                    logger.warning("[Reflect] Some plan steps remain in failed state.")
                    current_state = "FAILED"

        logger.info(f"[Orchestrator] GOAL EXECUTION FINISHED. Status: {current_state}")
        return state

    def _get_current_step(self, state: TaskState) -> Optional[PlanStep]:
        for step in state.plan:
            if step.status in [StepStatus.QUEUED, StepStatus.FAILED]:
                return step
        return None

    def _get_active_or_last_step(self, state: TaskState) -> Optional[PlanStep]:
        # Return currently running or last failed/succeeded step
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

            # Simple parameter heuristic modification for retry
            # e.g., if we hit a permission/locking collision, backoff-delay
            await asyncio.sleep(1.0 * (current_retries + 1))

            step.status = StepStatus.QUEUED  # Reset to allow re-execution
            return "EXECUTE"
        else:
            logger.error(f"[Self-Healing] Step {step.step_id} exceeded maximum retry envelope. Escalating to human, sir.")
            step.status = StepStatus.FAILED
            state.final_result = f"Step {step.step_id} failed permanently: {step.error or 'Verification check failed'}"
            return "FAILED"
