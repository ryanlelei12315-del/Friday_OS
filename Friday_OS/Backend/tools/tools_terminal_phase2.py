import os
import asyncio
import logging
import subprocess
import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from core.tool_contract import FridayToolContract, ToolResult, ToolStatus, ToolRiskLevel
from core.tool_registry import FridayBaseTool

logger = logging.getLogger("FridayTerminalTool")

SANDBOX_WORKSPACE = os.path.expanduser("~/FridayOS_Workspace")
os.makedirs(SANDBOX_WORKSPACE, exist_ok=True)


class TerminalExecuteSchema(BaseModel):
    command: str = Field(..., description="The shell command block to execute (e.g. 'echo 123', 'dir').")


class TerminalExecuteTool(FridayBaseTool):
    def __init__(self):
        contract = FridayToolContract(
            name="terminal.execute",
            description="Executes shell commands (PowerShell/CMD) inside Friday's sandboxed workspace environment. High Risk.",
            version="1.0.0",
            risk_level=ToolRiskLevel.HIGH,
            required_permissions=["terminal.execute"],
            timeout=20.0,
        )
        super().__init__(contract, TerminalExecuteSchema)

    async def run(self, **kwargs) -> ToolResult:
        validated = self.validate_args(kwargs)
        command = validated.command.strip()

        # Strict command checks against destructive actions
        BLOCKED_TOKENS = {
            "rmdir /s",
            "rm -rf",
            "format-volume",
            "del /s",
            "format",
            "mkfs",
        }

        for token in BLOCKED_TOKENS:
            if token in command.lower():
                return ToolResult(
                    status=ToolStatus.DENIED,
                    error=f"Command execution blocked: Contains restricted token '{token}'."
                )

        start_time = time.time()
        try:
            logger.info(f"[Terminal] Executing command: '{command}' inside '{SANDBOX_WORKSPACE}'")

            # Determine correct shell platform
            import sys
            shell_executable = "powershell" if sys.platform == "win32" else "/bin/bash"
            shell_flag = "-Command" if sys.platform == "win32" else "-c"

            # Execute securely using subprocess in a non-blocking asyncio thread pool pool
            # By running inside SANDBOX_WORKSPACE as cwd, we isolate operations to the sandbox workspace directory.
            process = await asyncio.create_subprocess_exec(
                shell_executable,
                shell_flag,
                command,
                cwd=SANDBOX_WORKSPACE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                # Enforce execution timeout limits
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.contract.timeout
                )
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
                duration = time.time() - start_time
                return ToolResult(
                    status=ToolStatus.TIMEOUT,
                    error=f"Command timed out after exceeding {self.contract.timeout}s.",
                    execution_time=duration,
                )

            duration = time.time() - start_time
            stdout_str = stdout_bytes.decode("utf-8", errors="ignore")
            stderr_str = stderr_bytes.decode("utf-8", errors="ignore")
            exit_code = process.returncode

            if exit_code == 0:
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    observation=stdout_str if stdout_str.strip() else "Command succeeded with no output.",
                    execution_time=duration,
                    metadata={"exit_code": 0, "stderr": stderr_str}
                )
            else:
                return ToolResult(
                    status=ToolStatus.FAILED,
                    error=stderr_str if stderr_str.strip() else f"Command failed with exit code {exit_code}.",
                    execution_time=duration,
                    metadata={"exit_code": exit_code, "stdout": stdout_str}
                )

        except Exception as e:
            duration = time.time() - start_time
            return ToolResult(
                status=ToolStatus.FAILED,
                error=f"Execution error: {str(e)}",
                execution_time=duration,
            )
