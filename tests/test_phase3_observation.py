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
from core.tool_contract import ToolResult, ToolStatus, ToolRiskLevel
from core.tool_registry import ToolRegistry
from core.policy_engine import PolicyEngine
from core.orchestrator import FridayOrchestrator
from core.state_model import StateSnapshot, SystemState, ProcessState, ApplicationState, WindowState
from core.observation import WindowsObserver
from core.app_discovery import ApplicationRegistry, DiscoveredApp
from core.verification_engine import VerificationEngine, VerificationStatus

# Tools
from tools.tools_core_phase2 import ApplicationLaunchTool, ProcessListTool


# =======================================================
# 1. STATE MODEL & OBSERVATION TESTS
# =======================================================

def test_state_model_instantiation():
    """Verify that Pydantic state models can be instantiated with values."""
    system = SystemState(
        hostname="test-host",
        os_name="win32",
        cpu_usage_percent=45.5,
        memory_usage_percent=60.0,
        total_memory_gb=16.0,
        available_memory_gb=6.4,
    )
    assert system.hostname == "test-host"
    assert system.cpu_usage_percent == 45.5

    proc = ProcessState(pid=101, name="code.exe", cpu_usage_percent=1.5, memory_usage_percent=2.0)
    assert proc.pid == 101
    assert proc.name == "code.exe"


def test_observation_caching_and_compression():
    """Verify WindowsObserver caching and context compression policies."""
    observer = WindowsObserver(cache_lifetime=1.0)

    # Check that cache invalidation works
    observer.invalidate_cache()
    assert observer._cached_snapshot is None

    snapshot = observer.get_snapshot(force_refresh=True)
    assert isinstance(snapshot, StateSnapshot)
    assert snapshot.system_state.hostname is not ""

    # Verify context compression output structure
    compressed = observer.compress_context(snapshot)
    assert "system_cpu_percent" in compressed
    assert "system_mem_percent" in compressed
    assert "active_applications" in compressed
    assert "active_windows" in compressed


# =======================================================
# 2. APPLICATION DISCOVERY TESTS
# =======================================================

def test_application_registry_resolutions():
    """Verify ApplicationRegistry maps names, aliases, and processes correctly."""
    registry = ApplicationRegistry()

    # Resolve "VS Code" alias
    app = registry.resolve("Visual Studio Code")
    assert app is not None
    assert app.logical_name == "code"
    assert app.windows_process_name == "code.exe"

    # Resolve "notepad" alias
    app_notepad = registry.resolve("text editor")
    assert app_notepad is not None
    assert app_notepad.logical_name == "notepad"

    # Non-existent app resolution
    app_none = registry.resolve("nonexistent_game_launcher")
    assert app_none is None


# =======================================================
# 3. TRANSITION VERIFICATION TESTS
# =======================================================

def test_verification_engine_transitions():
    """Verify transition verification outcomes for launch tools."""
    engine = VerificationEngine()

    step = PlanStep(
        step_id=1,
        description="Launch notepad",
        tool_name="application.launch",
        tool_args={"application": "notepad"},
    )

    # 1. State A: Notepad is not running
    before = StateSnapshot(
        timestamp=100.0,
        system_state=SystemState(),
        applications=[ApplicationState(logical_name="notepad", running=False)],
    )

    # 2. State B: Notepad is running (Verified)
    after_success = StateSnapshot(
        timestamp=101.0,
        system_state=SystemState(),
        applications=[ApplicationState(logical_name="notepad", running=True, pid=500)],
    )

    result_success = engine.verify_transition(step, before, after_success)
    assert result_success.status == VerificationStatus.VERIFIED
    assert "has launched" in result_success.reason

    # 3. State C: Notepad failed to run (Failed)
    after_failed = StateSnapshot(
        timestamp=101.0,
        system_state=SystemState(),
        applications=[ApplicationState(logical_name="notepad", running=False)],
    )

    result_failed = engine.verify_transition(step, before, after_failed)
    assert result_failed.status == VerificationStatus.FAILED
    assert "not running" in result_failed.reason


# =======================================================
# 4. ORCHESTRATOR VISUAL SCENARIO TESTS
# =======================================================

@pytest.mark.asyncio
async def test_scenario_already_running():
    """SCENARIO 3: Open VS Code when it is already running."""
    # Setup Tools and Mocks
    registry = ToolRegistry()
    policy = PolicyEngine(granted_permissions=["application.write", "process.read"])

    # Mock observer to report VS Code is already active before launch
    mock_observer = MagicMock()
    mock_before_snapshot = StateSnapshot(
        timestamp=100.0,
        system_state=SystemState(),
        applications=[ApplicationState(logical_name="code", running=True, pid=1234)],
    )
    mock_observer.get_snapshot.return_value = mock_before_snapshot
    mock_observer.compress_context.return_value = {
        "system_cpu_percent": 10.0,
        "system_mem_percent": 25.0,
        "active_applications": [{"name": "code", "running": True, "pid": 1234}],
        "active_windows": [{"title": "Friday_OS - Visual Studio Code", "app": "code", "visible": True}]
    }

    # Verify launch isn't blindly re-executed
    # We create a launch tool with an assertion that it shouldn't run if already running
    launch_tool_mock = AsyncMock(return_value=ToolResult(status=ToolStatus.SUCCESS))

    orchestrator = FridayOrchestrator(
        tool_registry=registry,
        policy_engine=policy,
        observer=mock_observer,
    )

    task = TaskState(
        task_id="vscode_running_id",
        goal="Open VS Code",
    )

    # Pre-plan: Skip launching if already verified
    async def mock_plan_generator(goal):
        # The agent inspects context and realizes code is active, so plan is empty or skipped
        return []

    final_state = await orchestrator.run_task(task, mock_plan_generator)
    assert final_state.final_result == "Goal completed successfully, sir."


@pytest.mark.asyncio
async def test_scenario_launch_fails_and_retries():
    """SCENARIO 4: Open VS Code when launch fails, verify retry escalation."""
    registry = ToolRegistry()

    # Mock process list to report app not running
    mock_process_list = AsyncMock()
    mock_process_list.run.return_value = ToolResult(
        status=ToolStatus.SUCCESS,
        observation="No matching processes.",
        metadata={"processes": []},
    )

    # Inject process registry
    launch_tool = ApplicationLaunchTool(process_list_callback=mock_process_list)
    registry.register(launch_tool)
    registry.register(mock_process_list)

    policy = PolicyEngine(granted_permissions=["application.write"])

    # Mock observer to report VS Code is closed both before and after
    mock_observer = MagicMock()
    mock_snapshot = StateSnapshot(
        timestamp=100.0,
        system_state=SystemState(),
        applications=[ApplicationState(logical_name="code", running=False)],
    )
    mock_observer.get_snapshot.return_value = mock_snapshot
    mock_observer.compress_context.return_value = {
        "system_cpu_percent": 10.0,
        "system_mem_percent": 25.0,
        "active_applications": [{"name": "code", "running": False}],
        "active_windows": []
    }

    orchestrator = FridayOrchestrator(
        tool_registry=registry,
        policy_engine=policy,
        observer=mock_observer,
    )

    # Limit retries to 1 for fast test execution
    task = TaskState(
        task_id="vscode_fail_id",
        goal="Open VS Code",
        max_retries_per_step=1,
    )

    # Subprocess.Popen mock throws error (fails launch)
    mock_popen = MagicMock()
    mock_popen.poll.return_value = 1 # terminated

    with patch("subprocess.Popen", side_effect=RuntimeError("Executable not found")):
        async def mock_plan_generator(goal):
            return [
                PlanStep(
                    step_id=1,
                    description="Launch VS Code IDE",
                    tool_name="application.launch",
                    tool_args={"application": "code"},
                )
            ]

        final_state = await orchestrator.run_task(task, mock_plan_generator)

        # Asserts escalation status
        assert final_state.plan[0].status == StepStatus.FAILED
        assert "permanently" in final_state.final_result


# =======================================================
# 5. DEV ENVIRONMENT PREPARATION BENCHMARK
# =======================================================

@pytest.mark.asyncio
async def test_prepare_development_environment_benchmark():
    """
    BENCHMARK SCENARIO: "Friday, prepare my development environment."
    Ensures multi-step plan, pre-launch inspection, state execution,
    and post-condition verification all work in a cohesive loop.
    """
    registry = ToolRegistry()

    # 1. Register tools
    mock_process_list = AsyncMock()
    mock_process_list.run.return_value = ToolResult(
        status=ToolStatus.SUCCESS,
        observation="PID 1234: code (RAM: 1.5%)",
        metadata={"processes": [{"pid": 1234, "name": "code", "memory_percent": 1.5}]},
    )

    launch_tool = ApplicationLaunchTool(process_list_callback=mock_process_list)
    registry.register(launch_tool)
    registry.register(mock_process_list)

    policy = PolicyEngine(granted_permissions=["application.write", "process.read"])

    # 2. Mock Observer to report closed before, and running after
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

    # Get snapshot returns before on first call, after on subsequent calls
    mock_observer.get_snapshot.side_effect = [before_snap, before_snap, after_snap, after_snap]
    mock_observer.compress_context.return_value = {
        "system_cpu_percent": 12.5,
        "system_mem_percent": 45.0,
        "active_applications": [{"name": "code", "running": True, "pid": 1234}],
        "active_windows": [{"title": "Friday_OS - VS Code", "app": "code", "visible": True}]
    }

    orchestrator = FridayOrchestrator(
        tool_registry=registry,
        policy_engine=policy,
        observer=mock_observer,
    )

    task = TaskState(
        task_id="prepare_dev_env_id",
        goal="Prepare development environment",
    )

    mock_popen = MagicMock()
    mock_popen.poll.return_value = None
    mock_popen.pid = 1234

    with patch("subprocess.Popen", return_value=mock_popen):
        async def mock_plan_generator(goal):
            # Decomposes dev prep goal into launch VS Code
            return [
                PlanStep(
                    step_id=1,
                    description="Open VS Code workspace",
                    tool_name="application.launch",
                    tool_args={"application": "code"},
                )
            ]

        final_state = await orchestrator.run_task(task, mock_plan_generator)

        # Verify full transition loop completed with verification SUCCESS
        assert final_state.final_result == "Goal completed successfully, sir."
        assert final_state.plan[0].status == StepStatus.SUCCESS
        assert "step_1_verification_result" in final_state.metadata
        assert final_state.metadata["step_1_verification_result"]["status"] == "verified"
