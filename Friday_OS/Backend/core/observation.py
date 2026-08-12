import os
import sys
import time
import socket
import psutil
import logging
from typing import Any, Dict, List, Optional

from core.state_model import (
    SystemState,
    ProcessState,
    ApplicationState,
    WindowState,
    WorkspaceFile,
    WorkspaceState,
    NetworkConnection,
    NetworkState,
    StateSnapshot,
)

logger = logging.getLogger("FridayObserver")

SANDBOX_WORKSPACE = os.path.expanduser("~/FridayOS_Workspace")
os.makedirs(SANDBOX_WORKSPACE, exist_ok=True)


class WindowsObserver:
    def __init__(self, cache_lifetime: float = 2.0):
        """
        Manages high-fidelity Windows State Observation, caching snapshots
        to prevent heavy CPU/process list querying overhead, and compressing context.
        """
        self.cache_lifetime = cache_lifetime
        self._cached_snapshot: Optional[StateSnapshot] = None
        self._last_snapshot_time: float = 0.0

    def invalidate_cache(self) -> None:
        """Forcefully invalidates the active environment cache."""
        self._cached_snapshot = None
        self._last_snapshot_time = 0.0
        logger.info("[Observer] Cache explicitly invalidated.")

    def get_snapshot(self, force_refresh: bool = False) -> StateSnapshot:
        """
        Retrieves the latest StateSnapshot of the operating system.
        Uses cached snapshots if within the configured cache_lifetime.
        """
        now = time.time()
        if not force_refresh and self._cached_snapshot and (now - self._last_snapshot_time < self.cache_lifetime):
            logger.info("[Observer] Returning cached operating system snapshot.")
            return self._cached_snapshot

        logger.info("[Observer] Polling operating system to capture new StateSnapshot...")

        # 1. Gather System State
        cpu_usage = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        system = SystemState(
            hostname=socket.gethostname(),
            os_name=sys.platform,
            cpu_usage_percent=cpu_usage,
            memory_usage_percent=mem.percent,
            total_memory_gb=round(mem.total / (1024**3), 2),
            available_memory_gb=round(mem.available / (1024**3), 2),
        )

        # 2. Gather Process State (Capped to 100 entries to prevent context bloat)
        processes = []
        for proc in psutil.process_iter(["pid", "name", "memory_percent", "status"]):
            try:
                info = proc.info
                processes.append(
                    ProcessState(
                        pid=info["pid"],
                        name=info.get("name") or "unknown",
                        memory_usage_percent=round(info.get("memory_percent") or 0.0, 2),
                        status=info.get("status") or "running",
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if len(processes) >= 100:
                break

        # 3. Gather App State (Mapped to discovered statuses)
        apps = self._discover_applications(processes)

        # 4. Gather Window State (Mocked cleanly if non-Windows)
        windows = self._observe_window_state(processes)

        # 5. Gather Workspace Files State
        workspace = self._observe_workspace_state()

        # 6. Gather Network State
        network = self._observe_network_state()

        snapshot = StateSnapshot(
            timestamp=now,
            system_state=system,
            processes=processes,
            applications=apps,
            windows=windows,
            workspace_state=workspace,
            network_state=network,
        )

        self._cached_snapshot = snapshot
        self._last_snapshot_time = now
        return snapshot

    def compress_context(self, snapshot: StateSnapshot, relevant_app: Optional[str] = None) -> Dict[str, Any]:
        """
        COMPRESSION POLICY: Filter out non-relevant processes, files, or ports
        and return only high-value, bounded observations. Keeps LLM prompt small.
        """
        # System state is always useful
        compressed = {
            "system_cpu_percent": snapshot.system_state.cpu_usage_percent,
            "system_mem_percent": snapshot.system_state.memory_usage_percent,
        }

        # Filter applications: show all discovered standard ones
        compressed["active_applications"] = [
            {"name": app.logical_name, "running": app.running, "pid": app.pid}
            for app in snapshot.applications
        ]

        # Filter processes: only show the running app process or ones exceeding 1% RAM usage
        key_processes = []
        for p in snapshot.processes:
            is_relevant = relevant_app and relevant_app.lower() in p.name.lower()
            if is_relevant or p.memory_usage_percent > 1.0:
                key_processes.append({"pid": p.pid, "name": p.name, "ram_percent": p.memory_usage_percent})
        compressed["high_memory_processes"] = key_processes

        # Filter active windows: show focused and visible windows
        compressed["active_windows"] = [
            {"title": w.title, "app": w.application_name, "focused": w.focused}
            for w in snapshot.windows if w.visible
        ]

        # Workspace summary: list folder files briefly
        if snapshot.workspace_state:
            compressed["workspace_files"] = [
                f.relative_path for f in snapshot.workspace_state.files[:10]
            ]

        # Network connections summary
        if snapshot.network_state:
            active_ports = [conn.local_port for conn in snapshot.network_state.active_connections if conn.status == "LISTEN"]
            compressed["listening_ports"] = active_ports[:5]

        return compressed

    def _discover_applications(self, active_processes: List[ProcessState]) -> List[ApplicationState]:
        """Discovers active and installed application states."""
        # Simple, deterministic application statuses
        standard_apps = ["code", "notepad", "chrome"]
        apps = []

        running_names = {p.name.lower() for p in active_processes}

        for name in standard_apps:
            # Check if running
            pid = None
            is_running = False
            for p in active_processes:
                if name in p.name.lower() or (name == "code" and "vscode" in p.name.lower()):
                    is_running = True
                    pid = p.pid
                    break

            apps.append(
                ApplicationState(
                    logical_name=name,
                    executable=name,
                    installed=True, # Default installed on Windows Sandbox / Workspace environment
                    running=is_running,
                    pid=pid,
                )
            )
        return apps

    def _observe_window_state(self, active_processes: List[ProcessState]) -> List[WindowState]:
        """Observe active open window states, falling back gracefully if non-Windows."""
        windows = []
        if sys.platform == "win32":
            try:
                import win32gui
                import win32process

                # Callback to collect visible window properties
                def win_enum_callback(hwnd, extra):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if title.strip():
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            windows.append(
                                WindowState(
                                    title=title,
                                    visible=True,
                                    process_pid=pid,
                                    focused=(hwnd == win32gui.GetForegroundWindow()),
                                )
                            )
                win32gui.EnumWindows(win_enum_callback, None)
            except Exception as e:
                logger.warning(f"[Observer] Win32 window enumeration failed: {e}")
        else:
            # Graceful platform-agnostic fallback simulation
            # If 'code' or 'notepad' is running, simulate its active window representation
            for p in active_processes:
                if "code" in p.name.lower():
                    windows.append(WindowState(title="Friday_OS - Visual Studio Code", application_name="code", process_pid=p.pid, focused=True))
                elif "notepad" in p.name.lower():
                    windows.append(WindowState(title="Untitled - Notepad", application_name="notepad", process_pid=p.pid, focused=False))

        return windows

    def _observe_workspace_state(self) -> WorkspaceState:
        """Observe and list files inside our sandbox workspace."""
        files = []
        try:
            for root, _, filenames in os.walk(SANDBOX_WORKSPACE):
                for f in filenames:
                    abs_path = os.path.join(root, f)
                    rel_path = os.path.relpath(abs_path, SANDBOX_WORKSPACE)
                    files.append(
                        WorkspaceFile(
                            relative_path=rel_path,
                            size_bytes=os.path.getsize(abs_path),
                            modified_time=os.path.getmtime(abs_path),
                        )
                    )
                # Prevent deep infinite directory walk scans
                if len(files) >= 50:
                    break
        except Exception as e:
            logger.warning(f"[Observer] Workspace scanning failed: {e}")

        return WorkspaceState(sandbox_path=SANDBOX_WORKSPACE, files=files)

    def _observe_network_state(self) -> NetworkState:
        """Observe open ports and listening connections."""
        connections = []
        try:
            # List TCP connections safely
            for conn in psutil.net_connections(kind="tcp"):
                if conn.laddr:
                    connections.append(
                        NetworkConnection(
                            local_port=conn.laddr.port,
                            remote_ip=conn.raddr.ip if conn.raddr else "",
                            remote_port=conn.raddr.port if conn.raddr else None,
                            status=conn.status,
                        )
                    )
                if len(connections) >= 30:
                    break
        except Exception as e:
            logger.warning(f"[Observer] Network connection query failed: {e}")

        return NetworkState(active_connections=connections)
