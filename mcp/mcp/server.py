import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.tools.search import fast_local_search
from mcp.tools.system_ui import click_ui_element

mcp = FastMCP("filesystem")
mcp = FastMCP("FridayOS_Core")


@mcp.tool()
def list_directory(path: str) -> str:
    """
    List files and folders in a directory.
    """

    p = Path(path)

    if not p.exists():
        return "Directory does not exist."

    items = []

    for item in p.iterdir():
        items.append(item.name)

    return "\n".join(items)


@mcp.tool()
def read_text_file(path: str) -> str:
    """
    Read a text file.
    """

    p = Path(path)

    if not p.exists():
        return "File not found."

    return p.read_text(encoding="utf-8", errors="ignore")[:10000]


if __name__ == "__main__":
    mcp.run()


@mcp.tool()
def execute_powershell(command: str) -> str:
    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return result.stderr

        return result.stdout

    except Exception as e:
        return str(e)


@mcp.tool()
def search_desktop_files(query: str) -> str:
    """Instantly scan the entire hard drive for matching files or folders."""
    return fast_local_search(query)


@mcp.tool()
def interact_with_application(window_title: str, button_name: str) -> str:
    """Click buttons or interactive elements inside an active window."""
    return click_ui_element(window_title, button_name)


if __name__ == "__main__":
    mcp.run()
