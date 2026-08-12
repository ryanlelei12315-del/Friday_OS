import os
import sys
import psutil
import logging
import asyncio
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field

from core.tool_contract import FridayToolContract, ToolResult, ToolStatus, ToolRiskLevel
from core.tool_registry import FridayBaseTool

logger = logging.getLogger("FridayCoreTools")

# Enforce default sandbox path
SANDBOX_WORKSPACE = os.path.expanduser("~/FridayOS_Workspace")
os.makedirs(SANDBOX_WORKSPACE, exist_ok=True)


# ==========================================
# 1. Input Schemas (Pydantic Models)
# ==========================================

class EmptySchema(BaseModel):
    pass


class ProcessListSchema(BaseModel):
    filter_name: Optional[str] = Field(default=None, description="Optional process name substring filter.")


class ApplicationLaunchSchema(BaseModel):
    application: str = Field(..., description="The name of the application to launch (e.g. 'code', 'notepad').")


class FilesystemListSchema(BaseModel):
    directory: str = Field(default=".", description="The directory path to list. Defaults to workspace root.")


class FilesystemReadSchema(BaseModel):
    file_path: str = Field(..., description="The relative or absolute file path to read from workspace.")


# ==========================================
# Helper: Sandbox path verification
# ==========================================

def is_safe_path(target_path: str) -> bool:
    """
    Prevents path traversal attacks by validating that target_path resides
    strictly inside the designated FridayOS sandbox workspace.
    """
    try:
        # Resolve absolute paths
        abs_workspace = os.path.abspath(SANDBOX_WORKSPACE)

        # If relative, join with workspace root
        if not os.path.isabs(target_path):
            abs_target = os.path.abspath(os.path.join(abs_workspace, target_path))
        else:
            abs_target = os.path.abspath(target_path)

        # Check parent directory containment
        common = os.path.commonpath([abs_workspace, abs_target])
        return common == abs_workspace
    except Exception:
        return False


# ==========================================
# 2. Tools Implementations
# ==========================================

class SystemGetInfoTool(FridayBaseTool):
    def __init__(self):
        contract = FridayToolContract(
            name="system.get_info",
            description="Retrieve basic Windows system platform architecture and host information.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["system.read"],
            timeout=10.0,
        )
        super().__init__(contract, EmptySchema)

    async def run(self, **kwargs) -> ToolResult:
        try:
            info = {
                "platform": sys.platform,
                "os_name": os.name,
                "cpu_count": psutil.cpu_count(logical=True),
                "total_memory_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            }
            return ToolResult(
                status=ToolStatus.SUCCESS,
                observation=f"Windows Host platform: {info['platform']}, OS: {info['os_name']}, CPUs: {info['cpu_count']}, Memory: {info['total_memory_gb']} GB.",
                metadata=info,
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=str(e))


class SystemGetCpuUsageTool(FridayBaseTool):
    def __init__(self):
        contract = FridayToolContract(
            name="system.get_cpu_usage",
            description="Retrieve active CPU utilization percentage metrics.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["system.read"],
            timeout=5.0,
        )
        super().__init__(contract, EmptySchema)

    async def run(self, **kwargs) -> ToolResult:
        try:
            usage = psutil.cpu_percentage(interval=0.1)
            return ToolResult(
                status=ToolStatus.SUCCESS,
                observation=f"Current aggregate system CPU usage is {usage}%.",
                metadata={"cpu_usage_percent": usage},
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=str(e))


class SystemGetMemoryUsageTool(FridayBaseTool):
    def __init__(self):
        contract = FridayToolContract(
            name="system.get_memory_usage",
            description="Retrieve active virtual memory consumption percentage and details.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["system.read"],
            timeout=5.0,
        )
        super().__init__(contract, EmptySchema)

    async def run(self, **kwargs) -> ToolResult:
        try:
            mem = psutil.virtual_memory()
            return ToolResult(
                status=ToolStatus.SUCCESS,
                observation=f"Memory usage: {mem.percent}% of {round(mem.total / (1024**3), 2)} GB total (Available: {round(mem.available / (1024**3), 2)} GB).",
                metadata={
                    "total_gb": round(mem.total / (1024**3), 2),
                    "used_gb": round(mem.used / (1024**3), 2),
                    "available_gb": round(mem.available / (1024**3), 2),
                    "percent_used": mem.percent,
                },
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=str(e))


class ProcessListTool(FridayBaseTool):
    def __init__(self):
        contract = FridayToolContract(
            name="process.list",
            description="Retrieve lists of active system processes with PIDs and memory usage metrics.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["process.read"],
            timeout=10.0,
        )
        super().__init__(contract, ProcessListSchema)

    async def run(self, **kwargs) -> ToolResult:
        validated = self.validate_args(kwargs)
        filter_name = validated.filter_name
        try:
            processes = []
            for proc in psutil.process_iter(["pid", "name", "memory_percent"]):
                try:
                    info = proc.info
                    name = info.get("name") or ""
                    if filter_name and filter_name.lower() not in name.lower():
                        continue
                    processes.append({
                        "pid": info["pid"],
                        "name": name,
                        "memory_percent": round(info.get("memory_percent") or 0.0, 2)
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

                # Cap process lists to prevent context bloats
                if len(processes) >= 150:
                    break

            lines = [f"PID {p['pid']}: {p['name']} (RAM: {p['memory_percent']}%)" for p in processes]
            observation = "\n".join(lines) if lines else "No matching processes running."
            return ToolResult(
                status=ToolStatus.SUCCESS,
                observation=observation,
                metadata={"processes": processes},
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=str(e))


class ApplicationListTool(FridayBaseTool):
    def __init__(self):
        contract = FridayToolContract(
            name="application.list",
            description="Retrieve lists of pre-indexed and discoverable application profiles.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["application.read"],
            timeout=5.0,
        )
        super().__init__(contract, EmptySchema)

    async def run(self, **kwargs) -> ToolResult:
        # For simplicity, we expose standard validated apps
        apps = {
            "code": "VS Code editor",
            "notepad": "Notepad basic text editor",
            "chrome": "Google Chrome browser",
        }
        lines = [f"- {k}: {v}" for k, v in apps.items()]
        return ToolResult(
            status=ToolStatus.SUCCESS,
            observation="Available applications:\n" + "\n".join(lines),
            metadata=apps,
        )


class ApplicationLaunchTool(FridayBaseTool):
    def __init__(self, process_list_callback: Optional[Type[FridayBaseTool]] = None):
        contract = FridayToolContract(
            name="application.launch",
            description="Securely launch validated system applications (e.g. 'code', 'notepad') without shell command injections.",
            version="1.0.0",
            risk_level=ToolRiskLevel.MEDIUM,
            required_permissions=["application.write"],
            timeout=15.0,
        )
        super().__init__(contract, ApplicationLaunchSchema)
        self.process_list_tool = process_list_callback or ProcessListTool()

    async def run(self, **kwargs) -> ToolResult:
        validated = self.validate_args(kwargs)
        app = validated.application.lower().strip()

        # Restricted list of safe launch binaries
        SAFE_BINARIES = {
            "code": "code",
            "notepad": "notepad.exe",
            "notepad.exe": "notepad.exe",
            "chrome": "chrome",
        }

        if app not in SAFE_BINARIES:
            return ToolResult(
                status=ToolStatus.INVALID_INPUT,
                error=f"Unrecognized or restricted application target: '{app}'. Cannot launch."
            )

        binary_to_run = SAFE_BINARIES[app]
        try:
            logger.info(f"[ApplicationLaunch] Safe spawn binary: {binary_to_run}")
            # Spawn process securely without using shell=True to prevent cmd injection
            import subprocess
            proc = subprocess.Popen([binary_to_run], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Active Verification check!
            # Wait 1.5 seconds for process initialization
            await asyncio.sleep(1.5)

            # Let's inspect processes to verify success
            verify_res = await self.process_list_tool.run(filter_name=app)
            proc_running = "running" in verify_res.observation or len(verify_res.metadata.get("processes", [])) > 0

            if proc_running or proc.poll() is None:
                obs = f"Successfully launched {app}. Verification: Process is active."
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    observation=obs,
                    metadata={"process_running_verified": True, "pid_spawned": proc.pid}
                )
            else:
                obs = f"Process spawned for {app} but failed verification check (terminated immediately)."
                return ToolResult(
                    status=ToolStatus.FAILED,
                    error=obs,
                    metadata={"process_running_verified": False}
                )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=f"Launch failed: {str(e)}")


class FilesystemListTool(FridayBaseTool):
    def __init__(self):
        contract = FridayToolContract(
            name="filesystem.list",
            description="List contents of target directories inside the sandboxed workspace folder.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["filesystem.read"],
            timeout=10.0,
        )
        super().__init__(contract, FilesystemListSchema)

    async def run(self, **kwargs) -> ToolResult:
        validated = self.validate_args(kwargs)
        directory = validated.directory

        # Enforce sandbox safety
        target_dir = os.path.abspath(os.path.join(SANDBOX_WORKSPACE, directory))
        if not is_safe_path(target_dir):
            return ToolResult(
                status=ToolStatus.DENIED,
                error=f"Access Denied: Path '{directory}' is outside the authorized FridayOS workspace sandbox."
            )

        try:
            if not os.path.exists(target_dir):
                return ToolResult(status=ToolStatus.FAILED, error="Directory does not exist.")

            items = os.listdir(target_dir)
            observation = "\n".join(items) if items else "Directory is empty."
            return ToolResult(
                status=ToolStatus.SUCCESS,
                observation=observation,
                metadata={"items": items, "absolute_directory_path": target_dir}
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=str(e))


class FilesystemReadTool(FridayBaseTool):
    def __init__(self):
        contract = FridayToolContract(
            name="filesystem.read",
            description="Read text contents of files safely within the sandboxed workspace folder.",
            version="1.0.0",
            risk_level=ToolRiskLevel.LOW,
            required_permissions=["filesystem.read"],
            timeout=10.0,
        )
        super().__init__(contract, FilesystemReadSchema)

    async def run(self, **kwargs) -> ToolResult:
        validated = self.validate_args(kwargs)
        file_path = validated.file_path

        # Enforce sandbox safety
        target_file = os.path.abspath(os.path.join(SANDBOX_WORKSPACE, file_path))
        if not is_safe_path(target_file):
            return ToolResult(
                status=ToolStatus.DENIED,
                error=f"Access Denied: Path '{file_path}' is outside the authorized FridayOS workspace sandbox."
            )

        try:
            if not os.path.exists(target_file):
                return ToolResult(status=ToolStatus.FAILED, error="File not found.")
            if os.path.isdir(target_file):
                return ToolResult(status=ToolStatus.INVALID_INPUT, error="Target is a directory, not a file.")

            with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read(8000)  # Safe buffer read cap

            return ToolResult(
                status=ToolStatus.SUCCESS,
                observation=text,
                metadata={"file_size_bytes": os.path.getsize(target_file)}
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.FAILED, error=str(e))
