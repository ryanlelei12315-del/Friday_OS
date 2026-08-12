import logging
from enum import Enum
from typing import List, Set, Tuple

from core.tool_contract import ToolRiskLevel, FridayToolContract

logger = logging.getLogger("FridayPolicyEngine")


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRES_APPROVAL = "requires_approval"


class PolicyEngine:
    def __init__(
        self,
        granted_permissions: List[str] = None,
        denied_permissions: List[str] = None,
        approval_required_risks: List[ToolRiskLevel] = None,
    ):
        """
        Policy Engine that governs tool executions.

        Args:
            granted_permissions: Permissions allowed on this session (e.g. ['system.read', 'filesystem.read'])
            denied_permissions: Permissions explicitly blocked.
            approval_required_risks: Risk levels that mandate user validation before running.
        """
        # Enforce defaults: if granted_permissions is None, allow common safe/read permissions
        self.granted_permissions: Set[str] = (
            set(granted_permissions)
            if granted_permissions is not None
            else {
                "system.read",
                "process.read",
                "filesystem.read",
                "application.read",
            }
        )
        self.denied_permissions: Set[str] = set(denied_permissions or [])

        # High and Critical risks require explicit approval by default
        self.approval_required_risks: Set[ToolRiskLevel] = (
            set(approval_required_risks)
            if approval_required_risks is not None
            else {ToolRiskLevel.MEDIUM, ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL}
        )

    def evaluate(self, contract: FridayToolContract) -> Tuple[PolicyDecision, str]:
        """
        Evaluates tool execution against active policies.
        Returns (Decision, Reason).
        """
        logger.info(f"[Policy] Evaluating tool '{contract.name}' (Risk: {contract.risk_level.value})")

        # 1. Check explicit Denylists first
        for perm in contract.required_permissions:
            if perm in self.denied_permissions:
                reason = f"Permission '{perm}' is explicitly denied by active security policy."
                logger.warning(f"[Policy] {reason}")
                return PolicyDecision.DENY, reason

        # 2. Check Granted Permissions (Capability checks)
        for perm in contract.required_permissions:
            if perm not in self.granted_permissions:
                reason = f"Missing required permission '{perm}'."
                logger.warning(f"[Policy] {reason}")
                return PolicyDecision.DENY, reason

        # 3. Check Risk Levels
        if contract.risk_level in self.approval_required_risks:
            reason = f"Tool risk level is '{contract.risk_level.value}', requiring human-in-the-loop approval."
            logger.info(f"[Policy] {reason}")
            return PolicyDecision.REQUIRES_APPROVAL, reason

        # 4. Standard Allow
        return PolicyDecision.ALLOW, "Tool conforms to all active security policies."
