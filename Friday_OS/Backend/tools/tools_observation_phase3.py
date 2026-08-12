import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from core.tool_contract import FridayToolContract, ToolResult, ToolStatus, ToolRiskLevel
from core.tool_registry import FridayBaseTool
from core.observation import WindowsObserver

logger = logging.getLogger("FridayObservationTools")


# ==========================================
# Input Schemas (Pydantic Models)
# ==========================================

class EmptySchema(BaseModel):
    pass


class ProcessInspectSchema(BaseModel):
    filter_name: Optional[str] = Field(default=None, description="Optional substring to filter processes by name.")


# ==========================================
# Tools Implementations
# ==========================================

class SystemInspectTool(FridayBaseTool):
    def __init__(self, observer: Optional[WindowsObserver] = None):
        contract = FridayToolContract(
            name="system.inspect",
            description="Inspect system platform, hostname, CPU percentage, and virtual memory metrics.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["system.read"],
            timeout=10.0,
        )
        super().__init__(contract, EmptySchema)
        self.observer = observer or WindowsObserver()

    async def run(self, **kwargs) -> ToolResult:
        try:
            snapshot = self.observer.get_snapshot(force_refresh=True)
            compressed = self.observer.compress_context(snapshot)
            obs = (
                f"Hostname: {snapshot.system_state.hostname}, Platform: {snapshot.system_state.os_name}. "
                f"CPU usage: {compressed['system_cpu_percent']}%, RAM usage: {compressed['system_mem_percent']}%."
            )
            return ToolResult(
                status=ToolStatus.SUCCESS,
                observation=obs,
                metadata=compressed,
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=str(e))


class ProcessInspectTool(FridayBaseTool):
    def __init__(self, observer: Optional[WindowsObserver] = None):
        contract = FridayToolContract(
            name="process.inspect",
            description="Inspect active system processes with matching names, PIDs, and RAM consumption.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["process.read"],
            timeout=10.0,
        )
        super().__init__(contract, ProcessInspectSchema)
        self.observer = observer or WindowsObserver()

    async def run(self, **kwargs) -> ToolResult:
        validated = self.validate_args(kwargs)
        filter_name = validated.filter_name
        try:
            snapshot = self.observer.get_snapshot(force_refresh=True)
            compressed = self.observer.compress_context(snapshot, relevant_app=filter_name)

            lines = [f"PID {p['pid']}: {p['name']} (RAM: {p['ram_percent']}%)" for p in compressed["high_memory_processes"]]
            obs = "\n".join(lines) if lines else f"No highly active processes matching '{filter_name or ''}' discovered."
            return ToolResult(
                status=ToolStatus.SUCCESS,
                observation=obs,
                metadata={"processes": compressed["high_memory_processes"]},
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=str(e))


class WindowListActiveTool(FridayBaseTool):
    def __init__(self, observer: Optional[WindowsObserver] = None):
        contract = FridayToolContract(
            name="window.list_active",
            description="List currently active open visible GUI window titles and focused application states.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["window.read"],
            timeout=10.0,
        )
        super().__init__(contract, EmptySchema)
        self.observer = observer or WindowsObserver()

    async def run(self, **kwargs) -> ToolResult:
        try:
            snapshot = self.observer.get_snapshot(force_refresh=True)
            compressed = self.observer.compress_context(snapshot)

            lines = [f"- '{w['title']}' (App: {w['app']}, Focused: {w['focused']})" for w in compressed["active_windows"]]
            obs = "Active visible GUI windows:\n" + "\n".join(lines) if lines else "No active visible windows found."
            return ToolResult(
                status=ToolStatus.SUCCESS,
                observation=obs,
                metadata={"active_windows": compressed["active_windows"]},
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=str(e))


class WorkspaceInspectTool(FridayBaseTool):
    def __init__(self, observer: Optional[WindowsObserver] = None):
        contract = FridayToolContract(
            name="workspace.inspect",
            description="Inspect all directory and file paths within the sandboxed FridayOS workspace sandbox.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["filesystem.read"],
            timeout=10.0,
        )
        super().__init__(contract, EmptySchema)
        self.observer = observer or WindowsObserver()

    async def run(self, **kwargs) -> ToolResult:
        try:
            snapshot = self.observer.get_snapshot(force_refresh=True)
            compressed = self.observer.compress_context(snapshot)

            files = compressed.get("workspace_files", [])
            obs = "Sandbox Workspace Files:\n" + "\n".join([f"- {f}" for f in files]) if files else "Sandbox Workspace is empty."
            return ToolResult(
                status=ToolStatus.SUCCESS,
                observation=obs,
                metadata={"files": files},
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=str(e))
