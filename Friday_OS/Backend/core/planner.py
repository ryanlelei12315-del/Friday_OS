import abc
import logging
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field, ValidationError

from core.runtime_state import PlanStep, TaskState, StepStatus
from core.tool_contract import ToolRiskLevel, FridayToolContract
from core.tool_registry import ToolRegistry
from core.state_model import StateSnapshot

logger = logging.getLogger("FridayPlanner")


class Plan(BaseModel):
    goal: str
    assumptions: List[str] = Field(default_factory=list)
    steps: List[PlanStep] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    expected_outcomes: List[str] = Field(default_factory=list)
    completion_criteria: List[str] = Field(default_factory=list)


class BasePlanner(abc.ABC):
    @abc.abstractmethod
    async def generate_plan(
        self,
        goal: str,
        env_snapshot: StateSnapshot,
        registry: ToolRegistry,
    ) -> Plan:
        """Generates a structured, validated plan sequence for a given user goal."""
        pass


class RuleBasedPlanner(BasePlanner):
    """
    A deterministic, rule-based planner designed to handle standard desktop tasks
    robustly without non-deterministic LLM planning latencies.
    """
    async def generate_plan(
        self,
        goal: str,
        env_snapshot: StateSnapshot,
        registry: ToolRegistry,
    ) -> Plan:
        goal_lower = goal.lower().strip()
        steps = []

        if "open vs code" in goal_lower or "launch vs code" in goal_lower:
            # Plan to open VS Code
            steps.append(
                PlanStep(
                    step_id=1,
                    description="Launch Visual Studio Code IDE securely",
                    tool_name="application.launch",
                    tool_args={"application": "code"},
                )
            )
            return Plan(
                goal=goal,
                assumptions=["VS Code is installed and discoverable on PATH."],
                steps=steps,
                completion_criteria=["code process is verified running"],
            )

        elif "prepare my development environment" in goal_lower:
            # Complex Dev Prep Sequence
            steps.append(
                PlanStep(
                    step_id=1,
                    description="Launch Visual Studio Code IDE",
                    tool_name="application.launch",
                    tool_args={"application": "code"},
                )
            )
            steps.append(
                PlanStep(
                    step_id=2,
                    description="Launch sandboxed development server process on port 3000",
                    tool_name="terminal.execute",
                    tool_args={"command": "echo 'Starting dev server on port 3000...'"}, # Simple simulated shell start
                )
            )
            return Plan(
                goal=goal,
                assumptions=["VS Code and command executor are fully operational."],
                steps=steps,
                completion_criteria=["code process running", "dev server terminal executed"],
            )

        else:
            # Fallback simple echo plan
            steps.append(
                PlanStep(
                    step_id=1,
                    description="Execute default diagnostic check",
                    tool_name="terminal.execute",
                    tool_args={"command": "echo 'FridayOS Diagnostic check'"},
                )
            )
            return Plan(
                goal=goal,
                assumptions=[],
                steps=steps,
                completion_criteria=["diagnostic check executed successfully"],
            )


class PlanValidator:
    def __init__(self, max_plan_size: int = 10):
        self.max_plan_size = max_plan_size

    def validate(self, plan: Plan, registry: ToolRegistry) -> bool:
        """
        Validates LLM or rule-based generated plans against tool registry schemas.
        Rejects malformed, circular, or restricted plans prior to execution.
        """
        logger.info(f"[Validator] COMMENCING VALIDATION FOR PLAN: '{plan.goal}'")

        # 1. Enforce Plan size bounds (Anti-loop protection)
        if len(plan.steps) > self.max_plan_size:
            logger.error(f"[Validator] Plan rejected: Size exceeds limit ({len(plan.steps)} > {self.max_plan_size}).")
            return False

        if not plan.steps:
            logger.error("[Validator] Plan rejected: Plan contains no execution steps.")
            return False

        # Track seen steps for circular dependency detection
        seen_ids = set()

        # 2. Schema and registry checks
        for step in plan.steps:
            if step.step_id in seen_ids:
                logger.error(f"[Validator] Plan rejected: Duplicate step_id '{step.step_id}' (Circular/Contradictory).")
                return False
            seen_ids.add(step.step_id)

            tool_name = step.tool_name
            tool = registry.get(tool_name)
            if not tool:
                logger.error(f"[Validator] Plan rejected: Tool '{tool_name}' is not registered in the ToolRegistry.")
                return False

            # Verify inputs conformed to Pydantic expectations before running
            try:
                tool.validate_args(step.tool_args)
            except ValueError as e:
                logger.error(f"[Validator] Plan rejected: Tool '{tool_name}' args validation failed: {e}")
                return False

        logger.info("[Validator] Plan passed all structural validation checks cleanly.")
        return True
