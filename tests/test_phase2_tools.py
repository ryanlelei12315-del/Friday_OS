import os
import sys
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from pydantic import BaseModel

# Add backend to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "Friday_OS", "Backend")
)

from core.runtime_state import TaskState, PlanStep, StepStatus
from core.tool_contract import ToolResult, ToolStatus, ToolRiskLevel, FridayToolContract
from core.tool_registry import ToolRegistry, FridayBaseTool
from core.policy_engine import PolicyEngine, PolicyDecision
from core.orchestrator import FridayOrchestrator

# Core tools imports
from tools.tools_core_phase2 import (
    SystemGetInfoTool,
    SystemGetCpuUsageTool,
    SystemGetMemoryUsageTool,
    ProcessListTool,
    ApplicationListTool,
    ApplicationLaunchTool,
    FilesystemListTool,
    FilesystemReadTool,
    SANDBOX_WORKSPACE,
    EmptySchema,
)
from tools.tools_terminal_phase2 import TerminalExecuteTool


# =======================================================
# 1. TOOL CONTRACT, REGISTRY, AND POLICY TESTS
# =======================================================

@pytest.mark.asyncio
async def test_low_risk_tool_execution():
    """TEST 1: Low-risk tool executes cleanly."""
    tool = SystemGetInfoTool()
    assert tool.contract.risk_level == ToolRiskLevel.LOW

    result = await tool.run()
    assert result.status == ToolStatus.SUCCESS
    assert "platform" in result.metadata
    assert "total_memory_gb" in result.metadata


@pytest.mark.asyncio
async def test_unknown_tool_rejection():
    """TEST 2: Unknown tool is rejected by orchestrator."""
    registry = ToolRegistry()
    policy = PolicyEngine()
    orchestrator = FridayOrchestrator(tool_registry=registry, policy_engine=policy)

    task = TaskState(
        task_id="unknown_tool_id",
        goal="Run fake tool",
        plan=[
            PlanStep(
                step_id=1,
                description="Run nonexistent tool",
                tool_name="fake.tool_name",
            )
        ]
    )

    async def dummy_plan(g):
        return task.plan

    final_state = await orchestrator.run_task(task, dummy_plan)
    assert final_state.plan[0].status == StepStatus.FAILED
    assert "not registered" in final_state.plan[0].error


@pytest.mark.asyncio
async def test_invalid_schema_rejection():
    """TEST 3: Invalid schema/arguments are rejected instantly."""
    registry = ToolRegistry()
    tool = FilesystemReadTool() # Expects file_path: str
    registry.register(tool)

    policy = PolicyEngine()
    orchestrator = FridayOrchestrator(tool_registry=registry, policy_engine=policy)

    task = TaskState(
        task_id="invalid_schema_id",
        goal="Read file with bad arguments",
        plan=[
            PlanStep(
                step_id=1,
                description="Read file",
                tool_name="filesystem.read",
                tool_args={"wrong_param": "some_value"}, # Missing file_path
            )
        ]
    )

    async def dummy_plan(g):
        return task.plan

    final_state = await orchestrator.run_task(task, dummy_plan)
    assert final_state.plan[0].status == StepStatus.FAILED
    assert "Validation failed" in final_state.plan[0].error


@pytest.mark.asyncio
async def test_high_risk_tool_policy_handling():
    """TEST 4 & 5: High-risk tool required approval, and denied tool never executes."""
    registry = ToolRegistry()
    tool = TerminalExecuteTool() # Risk: HIGH
    registry.register(tool)

    # Policy 1: DENY terminal execution permissions
    policy_deny = PolicyEngine(granted_permissions=["system.read"])
    orchestrator_deny = FridayOrchestrator(tool_registry=registry, policy_engine=policy_deny)

    task_deny = TaskState(
        task_id="deny_id",
        goal="Run terminal action",
        plan=[
            PlanStep(
                step_id=1,
                description="List workspace files",
                tool_name="terminal.execute",
                tool_args={"command": "echo 123"},
            )
        ]
    )

    async def dummy_plan(g):
        return task_deny.plan

    # Denied tool call
    final_deny = await orchestrator_deny.run_task(task_deny, dummy_plan)
    assert final_deny.plan[0].status == StepStatus.FAILED
    assert "Blocked" in final_deny.plan[0].error

    # Policy 2: REQUIRES_APPROVAL (granted permission but risk level high)
    policy_approve = PolicyEngine(granted_permissions=["terminal.execute"])
    orchestrator_approve = FridayOrchestrator(tool_registry=registry, policy_engine=policy_approve)

    # Case A: User rejects approval
    task_approve_reject = TaskState(
        task_id="approve_reject_id",
        goal="Run terminal action with approval",
        approval_state="rejected",
        plan=[
            PlanStep(
                step_id=1,
                description="List workspace files",
                tool_name="terminal.execute",
                tool_args={"command": "echo 123"},
            )
        ]
    )

    final_approve_reject = await orchestrator_approve.run_task(task_approve_reject, dummy_plan)
    assert final_approve_reject.plan[0].status == StepStatus.FAILED
    assert "rejected" in final_approve_reject.plan[0].error


# =======================================================
# 2. SANDBOX SECURITY & CONSTRAINT TESTS
# =======================================================

@pytest.mark.asyncio
async def test_filesystem_sandbox_traversal_boundaries():
    """TEST: Sandbox filesystem boundaries prevent traversal outside workspace."""
    list_tool = FilesystemListTool()
    read_tool = FilesystemReadTool()

    # Attempt directory list traversal
    res_list = await list_tool.run(directory="../../etc")
    assert res_list.status == ToolStatus.DENIED
    assert "outside the authorized FridayOS workspace sandbox" in res_list.error

    # Attempt absolute file read traversal
    res_read = await read_tool.run(file_path="/etc/passwd")
    assert res_read.status == ToolStatus.DENIED
    assert "outside the authorized FridayOS workspace sandbox" in res_read.error


# =======================================================
# 3. TIMEOUT & ERROR CAPTURE TESTS
# =======================================================

@pytest.mark.asyncio
async def test_tool_timeout_handling():
    """TEST 6: Tool execution timeouts are handled gracefully."""
    registry = ToolRegistry()

    # Custom tool that runs forever
    class SlowTool(FridayBaseTool):
        def __init__(self):
            contract = FridayToolContract(
                name="system.slow",
                description="Slow task simulator",
                timeout=0.1, # Short timeout
            )
            super().__init__(contract, EmptySchema)

        async def run(self, **kwargs) -> ToolResult:
            await asyncio.sleep(5.0)
            return ToolResult(status=ToolStatus.SUCCESS)

    registry.register(SlowTool())
    policy = PolicyEngine()
    orchestrator = FridayOrchestrator(tool_registry=registry, policy_engine=policy)

    task = TaskState(
        task_id="timeout_id",
        goal="Run slow action",
        plan=[
            PlanStep(
                step_id=1,
                description="Invoke slow operation",
                tool_name="system.slow",
            )
        ]
    )

    async def dummy_plan(g):
        return task.plan

    final_state = await orchestrator.run_task(task, dummy_plan)
    assert final_state.plan[0].status == StepStatus.FAILED
    assert "Timeout" in final_state.plan[0].error


# =======================================================
# 4. COMMAND INJECTION PROTECTION TESTS
# =======================================================

@pytest.mark.asyncio
async def test_arbitrary_shell_injection_rejection():
    """TEST 10: Restricted tokens/commands in terminal tool are rejected."""
    tool = TerminalExecuteTool()

    # Destructive token injection attempt
    res = await tool.run(command="rm -rf /")
    assert res.status == ToolStatus.DENIED
    assert "Command execution blocked: Contains restricted token" in res.error


# =======================================================
# 5. END-TO-END VERIFIED VALIDATION TESTSCENARIO
# =======================================================

@pytest.mark.asyncio
async def test_end_to_end_vscode_launch():
    """
    TEST 9 & 15: Open VS Code end-to-end validation.
    Runs TaskState -> PlanStep -> Tool Registry -> Policy Engine -> Execution -> Verification.
    """
    # 1. Initialize Registry and Policy Engines
    registry = ToolRegistry()

    # Mock ProcessListTool so it reports 'code' is running
    mock_processes = {
        "processes": [{"pid": 1234, "name": "code", "memory_percent": 1.5}]
    }
    mock_process_list = AsyncMock()
    mock_process_list.run.return_value = ToolResult(
        status=ToolStatus.SUCCESS,
        observation="PID 1234: code (RAM: 1.5%)",
        metadata=mock_processes,
    )

    # Register launch tool and inject mocked process listener
    launch_tool = ApplicationLaunchTool(process_list_callback=mock_process_list)
    registry.register(launch_tool)
    registry.register(mock_process_list)

    # Grant application launching permissions to policy engine
    policy = PolicyEngine(granted_permissions=["application.write"])
    orchestrator = FridayOrchestrator(tool_registry=registry, policy_engine=policy)

    # 2. Setup TaskState
    task = TaskState(
        task_id="vscode_e2e_id",
        goal="Open VS Code",
    )

    # Mocks subprocess.Popen so we don't spawn real OS processes during automated tests
    mock_popen = MagicMock()
    mock_popen.poll.return_value = None
    mock_popen.pid = 1234

    # 3. Trigger orchestrator control loop
    with patch("subprocess.Popen", return_value=mock_popen):
        # Initial step plan decomposition
        async def mock_plan_generator(goal):
            return [
                PlanStep(
                    step_id=1,
                    description="Launch validated VS Code IDE program",
                    tool_name="application.launch",
                    tool_args={"application": "code"},
                )
            ]

        final_state = await orchestrator.run_task(task, mock_plan_generator)

        # 4. Asserts and State updates validation
        assert final_state.final_result == "Goal completed successfully, sir."
        assert final_state.plan[0].status == StepStatus.SUCCESS
        assert "Successfully launched code" in final_state.plan[0].observation
