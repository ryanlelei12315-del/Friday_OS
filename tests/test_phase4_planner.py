import os
import sys
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "Friday_OS", "Backend")
)

from core.runtime_state import TaskState, PlanStep, StepStatus
from pydantic import BaseModel
from core.tool_contract import ToolResult, ToolStatus, ToolRiskLevel, FridayToolContract
from core.tool_registry import ToolRegistry, FridayBaseTool
from core.policy_engine import PolicyEngine
from core.orchestrator import FridayOrchestrator
from core.state_model import StateSnapshot, SystemState, ApplicationState, WindowState
from core.observation import WindowsObserver
from core.app_discovery import ApplicationRegistry
from core.verification_engine import VerificationEngine, VerificationStatus
from core.planner import Plan, RuleBasedPlanner, PlanValidator
from core.recovery_engine import RecoveryEngine, RecoveryAction, FailureCategory

# Tools
from tools.tools_core_phase2 import ApplicationLaunchTool, ProcessListTool
from tools.tools_terminal_phase2 import TerminalExecuteTool


# =======================================================
# 1. PLANNER & VALIDATION TESTS
# =======================================================

@pytest.mark.asyncio
async def test_planner_generation():
    """Verify that RuleBasedPlanner generates a structured plan."""
    planner = RuleBasedPlanner()
    registry = ToolRegistry()
    snapshot = StateSnapshot(timestamp=100.0, system_state=SystemState())

    plan = await planner.generate_plan("Open VS Code", snapshot, registry)
    assert isinstance(plan, Plan)
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "application.launch"


def test_plan_validator():
    """Verify that PlanValidator correctly validates and rejects malformed plans."""
    registry = ToolRegistry()
    registry.register(ApplicationLaunchTool())

    validator = PlanValidator(max_plan_size=2)

    # Case A: Valid Plan
    plan_valid = Plan(
        goal="Test goal",
        steps=[
            PlanStep(step_id=1, description="Launch", tool_name="application.launch", tool_args={"application": "code"})
        ]
    )
    assert validator.validate(plan_valid, registry) is True

    # Case B: Rejected due to size limits
    plan_oversized = Plan(
        goal="Too long",
        steps=[
            PlanStep(step_id=1, description="L1", tool_name="application.launch", tool_args={"application": "code"}),
            PlanStep(step_id=2, description="L2", tool_name="application.launch", tool_args={"application": "code"}),
            PlanStep(step_id=3, description="L3", tool_name="application.launch", tool_args={"application": "code"}),
        ]
    )
    assert validator.validate(plan_oversized, registry) is False

    # Case C: Rejected due to missing tool
    plan_bad_tool = Plan(
        goal="Bad tool",
        steps=[PlanStep(step_id=1, description="Bad", tool_name="nonexistent.tool")]
    )
    assert validator.validate(plan_bad_tool, registry) is False


# =======================================================
# 2. RECOVERY & ANTI-LOOP TESTS
# =======================================================

def test_recovery_classification():
    """Verify that RecoveryEngine classifies failures correctly."""
    engine = RecoveryEngine()

    step_timeout = PlanStep(step_id=1, description="A", error="Timeout exceeded")
    assert engine.classify_failure(step_timeout) == FailureCategory.TIMEOUT

    step_port = PlanStep(step_id=1, description="A", error="Address already in use / port occupied")
    assert engine.classify_failure(step_port) == FailureCategory.RESOURCE_UNAVAILABLE


@pytest.mark.asyncio
async def test_anti_loop_max_task_steps():
    """Verify orchestrator anti-loop protection triggers safe abort on step budget exceed."""
    registry = ToolRegistry()

    # Custom tool that fails and resets step to loop forever
    class LoopingTool(FridayBaseTool):
        def __init__(self):
                super().__init__(FridayToolContract(name="loop.tool", description="Mock looping tool"), EmptySchema)
        async def run(self, **kwargs) -> ToolResult:
            return ToolResult(status=ToolStatus.FAILED, error="Timeout on operation")

    class EmptySchema(BaseModel): pass

    registry.register(LoopingTool())

    # Bypass verification with fallback success=False to cause loop
    recovery = RecoveryEngine(max_step_retries=100)
    orchestrator = FridayOrchestrator(tool_registry=registry, recovery_engine=recovery)

    task = TaskState(
        task_id="loop_test_id",
        goal="Loop",
        max_retries_per_step=100, # Large retry count to test orchestrator's max_task_steps guard!
        plan=[PlanStep(step_id=1, description="Step 1", tool_name="loop.tool")]
    )

    async def dummy_plan(g):
        return task.plan

    # Running this task must hit the max_task_steps guard and terminate safely (not run infinitely)
    final_state = await orchestrator.run_task(task, dummy_plan)
    assert "Max step limit exceeded" in final_state.final_result


# =======================================================
# 3. CONSEQUENTIAL APPROVAL BARRIER TESTS
# =======================================================

@pytest.mark.asyncio
async def test_high_risk_approval_boundary():
    """Verify that HIGH risk operations require approval and abort if rejected."""
    registry = ToolRegistry()
    registry.register(TerminalExecuteTool()) # Risk: HIGH

    policy = PolicyEngine(granted_permissions=["terminal.execute"])
    orchestrator = FridayOrchestrator(tool_registry=registry, policy_engine=policy)

    task = TaskState(
        task_id="approve_boundary_id",
        goal="Run command",
        approval_state="rejected", # User rejects approval!
        plan=[
            PlanStep(step_id=1, description="Run code command", tool_name="terminal.execute", tool_args={"command": "dir"})
        ]
    )

    async def dummy_plan(g):
        return task.plan

    final_state = await orchestrator.run_task(task, dummy_plan)
    assert final_state.plan[0].status == StepStatus.FAILED
    assert "rejected" in final_state.plan[0].error


# =======================================================
# 4. THE DEFINITIVE PHASE 4 LONG-HORIZON E2E BENCHMARK
# =======================================================

@pytest.mark.asyncio
async def test_definitive_phase4_long_horizon_recovery_and_replan():
    """
    TEST 20: The Definitive Phase 4 E2E Test.
    Coordinates: PLAN -> EXECUTE -> OBSERVE -> FAIL -> RECOVER -> REPLAN -> VERIFY -> COMPLETE.

    Simulates:
    - VS Code initially closed.
    - Launching VS Code succeeds.
    - Starting server on Port 3000 fails (occupied port).
    - Recovery classifies as RESOURCE_UNAVAILABLE, recommends REPLAN.
    - Dynamic replan edits port args to Port 3001.
    - Spawning on Port 3001 succeeds.
    - Evidence postcondition verifications confirm COMPLETE.
    """
    registry = ToolRegistry()

    # 1. Register Mock tools
    mock_process_list = AsyncMock()
    mock_process_list.run.return_value = ToolResult(
        status=ToolStatus.SUCCESS,
        observation="PID 1234: code (RAM: 1.5%)",
        metadata={"processes": [{"pid": 1234, "name": "code", "memory_percent": 1.5}]},
    )

    launch_tool = ApplicationLaunchTool(process_list_callback=mock_process_list)
    registry.register(launch_tool)
    registry.register(mock_process_list)

    # Custom terminal execute mock representing port failures followed by success
    class MockTerminalExecuteTool(FridayBaseTool):
        def __init__(self):
            super().__init__(FridayToolContract(
                name="terminal.execute",
                description="Terminal executor",
                risk_level=ToolRiskLevel.HIGH,
                required_permissions=["terminal.execute"]
            ), TerminalExecuteSchema)

        async def run(self, **kwargs) -> ToolResult:
            cmd = kwargs.get("command", "")
            if "port 3000" in cmd.lower():
                # Represent portoccupied conflict!
                return ToolResult(
                    status=ToolStatus.FAILED,
                    error="Address already in use / port occupied"
                )
            else:
                # Port 3001 succeeds!
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    observation="Server started successfully on port 3001."
                )

    class TerminalExecuteSchema(BaseModel):
        command: str

    registry.register(MockTerminalExecuteTool())

    policy = PolicyEngine(granted_permissions=["application.write", "process.read", "terminal.execute"])

    # 2. Mock Observer to capture state changes
    mock_observer = MagicMock()
    before_snap = StateSnapshot(
        timestamp=100.0,
        system_state=SystemState(),
        applications=[ApplicationState(logical_name="code", running=False)],
    )
    after_snap = StateSnapshot(
        timestamp=101.0,
        system_state=SystemState(),
        applications=[ApplicationState(logical_name="code", running=True, pid=1234)],
    )
    # Observer cycles through snapshots
    mock_observer.get_snapshot.side_effect = [before_snap, before_snap, after_snap, after_snap, after_snap, after_snap, after_snap]
    mock_observer.compress_context.return_value = {
        "system_cpu_percent": 10.0,
        "system_mem_percent": 30.0,
        "active_applications": [{"name": "code", "running": True, "pid": 1234}],
        "active_windows": []
    }

    orchestrator = FridayOrchestrator(
        tool_registry=registry,
        policy_engine=policy,
        observer=mock_observer,
    )

    task = TaskState(
        task_id="long_horizon_dev_prep_id",
        goal="Prepare my development environment",
        approval_state="approved", # Automatically bypass approval for testing terminal run
    )

    mock_popen = MagicMock()
    mock_popen.poll.return_value = None
    mock_popen.pid = 1234

    with patch("subprocess.Popen", return_value=mock_popen):
        # Initial structured plan generation triggers RuleBasedPlanner
        final_state = await orchestrator.run_task(task)

        # 3. VERIFY FULL TRANSITION LIFECYCLE SUCCESS
        assert final_state.final_result == "Goal completed successfully, sir."

        # Step 1 should be success
        assert final_state.plan[0].status == StepStatus.SUCCESS

        # Step 2 should be success (repaired to Port 3001)
        assert final_state.plan[1].status == StepStatus.SUCCESS
        assert "port 3001" in final_state.plan[1].tool_args["command"]

        # Ensure dynamic replan counter was incremented
        assert final_state.metadata.get("replans_count") == 1
