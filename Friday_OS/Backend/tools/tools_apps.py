import json
import os
from pathlib import Path

import psutil
from livekit.agents import RunContext, function_tool
from rapidfuzz import process

APP_INDEX_FILE = "app_index.json"
PROTECTED_PROCESSES = {
    "explorer.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "dwm.exe",
    "system",
}


def build_app_index():

    apps = {}

    search_locations = [
        Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs",
        Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
        Path.home() / "Desktop",
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
    ]

    for location in search_locations:
        if not location.exists():
            continue

        try:
            for file in location.rglob("*"):
                if file.suffix.lower() not in [".lnk", ".exe"]:
                    continue

                name = file.stem.lower()

                if len(name) < 3:
                    continue

                if name not in apps:
                    apps[name] = str(file)

        except Exception:
            continue

    with open(APP_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(apps, f, indent=2)

    return len(apps)


def load_app_index():

    if not os.path.exists(APP_INDEX_FILE):
        build_app_index()

    with open(APP_INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@function_tool()
async def refresh_app_index(context: RunContext) -> str:
    """
    Scan Windows and rebuild the application index.
    """

    count = build_app_index()

    return f"Indexed {count} applications."


@function_tool()
async def open_application(context: RunContext, app_name: str) -> str:
    """
    Open an installed application.
    """

    try:
        apps = load_app_index()

        match = process.extractOne(app_name.lower(), list(apps.keys()))

        if not match:
            return "Application not found."

        matched_name = match[0]

        path = apps[matched_name]

        os.startfile(path)

        return f"Opened {matched_name}"

    except Exception as e:
        return str(e)


@function_tool()
async def list_running_apps(context: RunContext) -> str:
    """
    List running applications.
    """

    try:
        apps = []

        for proc in psutil.process_iter(["name"]):
            name = proc.info["name"]

            if name:
                apps.append(name)

        apps = sorted(set(apps))

        return "\n".join(apps[:300])

    except Exception as e:
        return str(e)


@function_tool()
async def is_app_running(context: RunContext, app_name: str) -> str:
    """
    Check if an application is running.
    """

    try:
        for proc in psutil.process_iter(["name"]):
            name = proc.info["name"]

            if not name:
                continue

            if app_name.lower() in name.lower():
                return f"{name} is running"

        return f"{app_name} is not running"

    except Exception as e:
        return str(e)


@function_tool()
async def close_application(context: RunContext, app_name: str) -> str:
    """
    Close a running application.
    """

    try:
        closed = []

        for proc in psutil.process_iter(["name"]):
            name = proc.info["name"]

            if not name:
                continue
            if name.lower() in PROTECTED_PROCESSES:
                continue

            if app_name.lower() in name.lower():
                proc.kill()
                closed.append(name)

        if not closed:
            return "No matching application found."

        return f"Closed {', '.join(closed)}"

    except Exception as e:
        return str(e)
