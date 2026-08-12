import os
import sys
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger("FridayAppDiscovery")


class DiscoveredApp(BaseModel):
    logical_name: str
    aliases: List[str]
    executable_name: str
    windows_process_name: str
    absolute_path: Optional[str] = None
    installed: bool = False
    version: str = "unknown"


class ApplicationRegistry:
    def __init__(self):
        """
        Manages discovery, mapping, and state validation of applications installed on the system,
        preventing blind arbitrary command executions.
        """
        self._apps: Dict[str, DiscoveredApp] = {}
        self._initialize_default_registry()

    def _initialize_default_registry(self) -> None:
        """Seed registry with common default target application profiles."""
        # Visual Studio Code
        self.register(
            DiscoveredApp(
                logical_name="code",
                aliases=["vs code", "vscode", "visual studio code", "code"],
                executable_name="code",
                windows_process_name="code.exe",
                installed=True,
            )
        )
        # Notepad
        self.register(
            DiscoveredApp(
                logical_name="notepad",
                aliases=["notepad", "notepad.exe", "text editor"],
                executable_name="notepad.exe",
                windows_process_name="notepad.exe",
                installed=True,
            )
        )
        # Google Chrome
        self.register(
            DiscoveredApp(
                logical_name="chrome",
                aliases=["chrome", "google chrome", "browser"],
                executable_name="chrome",
                windows_process_name="chrome.exe",
                installed=True,
            )
        )

    def register(self, app: DiscoveredApp) -> None:
        """Registers a discovered application profile."""
        self._apps[app.logical_name.lower()] = app
        logger.info(f"[Discovery] Registered app profile: {app.logical_name} (Executable: {app.executable_name})")

    def resolve(self, query: str) -> Optional[DiscoveredApp]:
        """
        Resolves a user-provided search string (alias) into a structured DiscoveredApp profile.
        Supports alias matching.
        """
        query_clean = query.lower().strip()

        # Direct key lookup
        if query_clean in self._apps:
            return self._apps[query_clean]

        # Alias matching
        for app in self._apps.values():
            if any(alias in query_clean or query_clean in alias for alias in app.aliases):
                return app

        return None

    def list_installed_apps(self) -> List[DiscoveredApp]:
        """Lists all applications successfully resolved as installed."""
        return [app for app in self._apps.values() if app.installed]

    def scan_system_shortcuts(self) -> int:
        """
        Scans standard Start Menu shortcut locations on real Windows systems
        to discover more installed executable aliases dynamically.
        """
        if sys.platform != "win32":
            logger.info("[Discovery] Non-Windows environment. Dynamic scanning skipped.")
            return 0

        count = 0
        search_locations = [
            os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        ]

        for loc in search_locations:
            if not os.path.exists(loc):
                continue
            try:
                for root, _, files in os.walk(loc):
                    for file in files:
                        if file.endswith(".lnk"):
                            stem = os.path.splitext(file)[0].lower()
                            # If not already registered, dynamically seed profile
                            if stem not in self._apps:
                                self.register(
                                    DiscoveredApp(
                                        logical_name=stem,
                                        aliases=[stem],
                                        executable_name=f"{stem}.exe",
                                        windows_process_name=f"{stem}.exe",
                                        installed=True,
                                    )
                                )
                                count += 1
            except Exception as e:
                logger.warning(f"[Discovery] Dynamic shortcut scan error on path '{loc}': {e}")
                continue

        return count
