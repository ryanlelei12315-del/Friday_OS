import logging
from enum import Enum
from typing import Tuple

from core.runtime_state import TaskState, PlanStep, StepStatus

logger = logging.getLogger("FridayRecoveryEngine")


class FailureCategory(str, Enum):
    INVALID_INPUT = "invalid_input"
    TOOL_UNAVAILABLE = "tool_unavailable"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    APPLICATION_FAILURE = "application_failure"
    VERIFICATION_FAILURE = "verification_failure"
    UNKNOWN_FAILURE = "unknown_failure"


class RecoveryAction(str, Enum):
    RETRY = "retry"
    REPLAN = "replan"
    ASK_USER = "ask_user"
    ABORT = "abort"


class RecoveryEngine:
    def __init__(self, max_step_retries: int = 3, max_total_replans: int = 3):
        self.max_step_retries = max_step_retries
        self.max_total_replans = max_total_replans

    def classify_failure(self, step: PlanStep) -> FailureCategory:
        """Classifies a failed step into our structured taxonomy."""
        err = (step.error or "").lower()
        obs = (step.observation or "").lower()

        if "validation" in err or "schema" in err or "invalid" in err:
            return FailureCategory.INVALID_INPUT
        elif "not registered" in err or "unavailable" in err:
            return FailureCategory.TOOL_UNAVAILABLE
        elif "blocked" in err or "denied" in err or "permission" in err:
            return FailureCategory.PERMISSION_DENIED
        elif "timeout" in err:
            return FailureCategory.TIMEOUT
        elif "occupied" in err or "in use" in err or "port" in err or "address already in use" in err:
            return FailureCategory.RESOURCE_UNAVAILABLE
        elif "launch" in err or "terminated" in err:
            return FailureCategory.APPLICATION_FAILURE
        elif "verification" in err or "verify" in err:
            return FailureCategory.VERIFICATION_FAILURE
        else:
            return FailureCategory.UNKNOWN_FAILURE

    def determine_recovery_action(
        self,
        step: PlanStep,
        state: TaskState,
    ) -> Tuple[RecoveryAction, str]:
        """
        Calculates the safest, non-looping recovery action to resolve a step failure.
        Enforces strict anti-loop limits.
        """
        category = self.classify_failure(step)
        logger.warning(f"[Recovery] Classifed step {step.step_id} failure as: {category.value.upper()}")

        # 1. Enforce strict Anti-Loop boundaries
        # Check step-level retries
        current_retries = state.retry_counts.get(step.step_id, 0)
        if current_retries >= self.max_step_retries:
            reason = f"Step {step.step_id} exceeded maximum retry envelope ({current_retries}/{self.max_step_retries}). Escalating."
            logger.error(f"[Recovery] {reason}")
            return RecoveryAction.ASK_USER, reason

        # Check plan-level dynamic replanning revisions
        current_replans = state.metadata.get("replans_count", 0)
        if current_replans >= self.max_total_replans:
            reason = f"Task exceeded maximum total plan revisions limit ({current_replans}/{self.max_total_replans}). Aborting safely."
            logger.error(f"[Recovery] {reason}")
            return RecoveryAction.ABORT, reason

        # 2. Map Failure category to Recovery strategy
        if category == FailureCategory.PERMISSION_DENIED:
            # Policy blocks or security boundaries must NEVER be retried autonomously
            reason = f"Security Policy Blocked execution of '{step.tool_name}'. Autonomy stops."
            return RecoveryAction.ABORT, reason

        elif category == FailureCategory.INVALID_INPUT:
            # Code/schema parameters must not be retried with identical arguments
            reason = f"Tool arguments failed schema parsing constraints. Escalating to human."
            return RecoveryAction.ASK_USER, reason

        elif category == FailureCategory.RESOURCE_UNAVAILABLE:
            # Resource conflicts (e.g. port occupied) represent excellent replanning candidates
            reason = f"Target resource is blocked/occupied. Recommending dynamic replan action."
            return RecoveryAction.REPLAN, reason

        elif category in [FailureCategory.TIMEOUT, FailureCategory.APPLICATION_FAILURE, FailureCategory.VERIFICATION_FAILURE]:
            # Transient failures can be safely retried with linear delay
            reason = f"Transient operation failure detected. Initiating retry attempt {current_retries + 1}."
            return RecoveryAction.RETRY, reason

        # Default fallback
        reason = "Unclassified or complex exception caught. Requesting manual human intervention."
        return RecoveryAction.ASK_USER, reason
