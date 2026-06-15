import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("filesystem")


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
