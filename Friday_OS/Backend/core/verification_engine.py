import logging
from enum import Enum
from typing import Optional
from pydantic import BaseModel

from core.runtime_state import PlanStep, StepStatus
from core.state_model import StateSnapshot

logger = logging.getLogger("FridayVerificationEngine")


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class VerificationResult(BaseModel):
    status: VerificationStatus
    reason: str
    before_state_summary: Optional[str] = None
    after_state_summary: Optional[str] = None


class VerificationEngine:
    def __init__(self):
        """
        Action Verification Engine. Evaluates transition boundaries:
        State A (Before Action) -> Action -> State B (After Action)
        to cleanly assert outcome success, failure, or inconclusive states.
        """
        pass

    def verify_transition(
        self,
        step: PlanStep,
        before: StateSnapshot,
        after: StateSnapshot,
    ) -> VerificationResult:
        """
        Asserts state transition outcomes based on the tool executed.
        """
        tool_name = step.tool_name
        logger.info(f"[Verification] Evaluating transition for step {step.step_id} using tool '{tool_name}'")

        if tool_name == "application.launch":
            app_target = step.tool_args.get("application", "").lower().strip()

            # Check application state before
            was_running = False
            for app in before.applications:
                if app.logical_name == app_target and app.running:
                    was_running = True
                    break

            # Check application state after
            is_running_now = False
            spawned_pid = None
            for app in after.applications:
                if app.logical_name == app_target and app.running:
                    is_running_now = True
                    spawned_pid = app.pid
                    break

            before_sum = f"{app_target} running = {was_running}"
            after_sum = f"{app_target} running = {is_running_now} (PID: {spawned_pid})"

            if is_running_now:
                if was_running:
                    reason = f"Application '{app_target}' was already running and remains active (Verified)."
                else:
                    reason = f"Successfully verified transition: Application '{app_target}' has launched (PID: {spawned_pid})."
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    reason=reason,
                    before_state_summary=before_sum,
                    after_state_summary=after_sum,
                )
            else:
                reason = f"Verification failed: Application '{app_target}' is not running post-execution."
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    reason=reason,
                    before_state_summary=before_sum,
                    after_state_summary=after_sum,
                )

        elif tool_name == "terminal.execute":
            # For terminal, check if exit_code is successful (zero)
            exit_code = step.observation # Mapped via output
            if step.status == StepStatus.SUCCESS:
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    reason="Command executed cleanly with zero exit code (Verified).",
                    before_state_summary="Terminal idle",
                    after_state_summary="Command succeeded",
                )
            else:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    reason=f"Command execution failed: {step.error or 'unknown exit status'}.",
                    before_state_summary="Terminal idle",
                    after_state_summary="Command execution failed",
                )

        # Fallback default verification: tool completed without error
        if step.status == StepStatus.SUCCESS:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                reason="Step completed successfully without errors.",
                before_state_summary="Step Queued",
                after_state_summary="Step Completed",
            )
        elif step.status == StepStatus.FAILED:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                reason=f"Step failed with error: {step.error or 'unknown'}.",
                before_state_summary="Step Queued",
                after_state_summary="Step Failed",
            )
        else:
            return VerificationResult(
                status=VerificationStatus.INCONCLUSIVE,
                reason="Execution status is inconclusive (no explicit verify metrics).",
                before_state_summary="Step Queued",
                after_state_summary="Step Pending",
            )
