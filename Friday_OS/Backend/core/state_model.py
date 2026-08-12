from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SystemState(BaseModel):
    hostname: str = ""
    os_name: str = ""
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    total_memory_gb: float = 0.0
    available_memory_gb: float = 0.0


class ProcessState(BaseModel):
    pid: int
    name: str
    executable: str = ""
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    status: str = ""


class ApplicationState(BaseModel):
    logical_name: str
    executable: str = ""
    installed: bool = False
    running: bool = False
    pid: Optional[int] = None
    version: str = "unknown"


class WindowState(BaseModel):
    title: str = ""
    application_name: str = ""
    process_pid: Optional[int] = None
    visible: bool = True
    focused: bool = False


class WorkspaceFile(BaseModel):
    relative_path: str
    size_bytes: int
    modified_time: float


class WorkspaceState(BaseModel):
    sandbox_path: str
    files: List[WorkspaceFile] = Field(default_factory=list)


class NetworkConnection(BaseModel):
    local_port: int
    remote_ip: str = ""
    remote_port: Optional[int] = None
    status: str = ""


class NetworkState(BaseModel):
    active_connections: List[NetworkConnection] = Field(default_factory=list)


class StateSnapshot(BaseModel):
    timestamp: float
    system_state: SystemState
    processes: List[ProcessState] = Field(default_factory=list)
    applications: List[ApplicationState] = Field(default_factory=list)
    windows: List[WindowState] = Field(default_factory=list)
    workspace_state: Optional[WorkspaceState] = None
    network_state: Optional[NetworkState] = None
