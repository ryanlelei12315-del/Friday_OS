import asyncio
import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock

# Add backend to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "Friday_OS", "Backend")
)

from core.runtime_state import TaskState, PlanStep, StepStatus
from core.orchestrator import FridayOrchestrator


@pytest.mark.asyncio
async def test_successful_orchestration():
    """Verify orchestrator runs through a multi-step plan cleanly to success."""
    # Define simple mock tools
    mock_tool_run = AsyncMock(return_value="VS Code focused")
    tools = {"open_vscode": mock_tool_run}

    orchestrator = FridayOrchestrator(tool_registry=tools)

    # Initial task state with a 1-step plan already populated
    task = TaskState(
        task_id="test_success_id",
        goal="Open VS Code",
        plan=[
            PlanStep(
                step_id=1,
                description="Launch VS Code app",
                tool_name="open_vscode",
                tool_args={"app_name": "VS Code"},
            )
        ],
    )

    # Dummy plan generator
    async def dummy_plan_generator(goal):
        return task.plan

    # Run orchestrator
    final_state = await orchestrator.run_task(
        state=task, plan_generator=dummy_plan_generator
    )

    # Asserts
    assert final_state.final_result == "Goal completed successfully, sir."
    assert final_state.plan[0].status == StepStatus.SUCCESS
    assert final_state.plan[0].observation == "VS Code focused"
    mock_tool_run.assert_called_once_with(app_name="VS Code")


@pytest.mark.asyncio
async def test_custom_verification_success():
    """Verify custom verifier determines step outcome."""
    mock_tool_run = AsyncMock(return_value="Launched browser")
    tools = {"launch_browser": mock_tool_run}

    # Custom verifier returns True (success)
    mock_verifier = AsyncMock(return_value=True)
    verifiers = {"verify_browser_active": mock_verifier}

    orchestrator = FridayOrchestrator(tool_registry=tools, verification_registry=verifiers)

    task = TaskState(
        task_id="test_verify_id",
        goal="Open Google",
        plan=[
            PlanStep(
                step_id=1,
                description="Launch chrome website browser",
                tool_name="launch_browser",
                tool_args={"url": "https://google.com"},
                verification_check="verify_browser_active",
            )
        ],
    )

    async def dummy_plan_generator(goal):
        return task.plan

    final_state = await orchestrator.run_task(
        state=task, plan_generator=dummy_plan_generator
    )

    assert final_state.plan[0].status == StepStatus.SUCCESS
    mock_verifier.assert_called_once()


@pytest.mark.asyncio
async def test_self_healing_and_failure():
    """Verify orchestrator retries on failure and eventually escalates."""
    # Tool throws exception on every run
    mock_tool_run = AsyncMock(side_effect=RuntimeError("Connection refused"))
    tools = {"start_server": mock_tool_run}

    orchestrator = FridayOrchestrator(tool_registry=tools)

    # Configure step with 2 max retries to make the test run faster
    task = TaskState(
        task_id="test_healing_id",
        goal="Start development server",
        max_retries_per_step=2,
        plan=[
            PlanStep(
                step_id=1,
                description="Spin up local dev server on port 3000",
                tool_name="start_server",
            )
        ],
    )

    async def dummy_plan_generator(goal):
        return task.plan

    final_state = await orchestrator.run_task(
        state=task, plan_generator=dummy_plan_generator
    )

    # Asserts
    # Should run 1 initial try + 2 retries = 3 total tool calls
    assert mock_tool_run.call_count == 3
    assert final_state.plan[0].status == StepStatus.FAILED
    assert "permanently" in final_state.final_result
    assert final_state.retry_counts[1] == 2  # step 1 retry count should be 2
