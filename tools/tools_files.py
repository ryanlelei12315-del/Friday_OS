import shutil
from pathlib import Path

from livekit.agents import RunContext, function_tool


@function_tool()
async def list_files(
    context: RunContext,  # type: ignore
    directory: str,
) -> str:
    """
    List files in a directory.
    """

    try:
        path = Path(directory)

        if not path.exists():
            return f"Directory not found: {directory}"

        files = []

        for item in path.iterdir():
            files.append(item.name)

        if not files:
            return "Directory is empty."

        return "\n".join(files)

    except Exception as e:
        return str(e)


@function_tool()
async def find_file(
    context: RunContext, filename: str, root_directory: str = "C:/Users"
) -> str:
    """
    Search for a file by name.
    """
    try:
        root = Path(root_directory)

        matches = []

        for file in root.rglob("*"):
            if filename.lower() in file.name.lower():
                matches.append(str(file))

            if len(matches) >= 20:
                break

        if not matches:
            return "No matching files found."

        return "\n".join(matches)

    except Exception as e:
        return str(e)


@function_tool()
async def create_file(context: RunContext, file_path: str, content: str = "") -> str:
    """
    Create a file.
    """

    try:
        path = Path(file_path)

        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content)

        return f"Created file: {file_path}"

    except Exception as e:
        return str(e)


@function_tool()
async def read_file(context: RunContext, file_path: str) -> str:
    """
    Read a text file.
    """

    try:
        path = Path(file_path)

        if not path.exists():
            return "File not found."

        return path.read_text(encoding="utf-8", errors="ignore")[:5000]

    except Exception as e:
        return str(e)


@function_tool()
async def move_file(context: RunContext, source: str, destination: str) -> str:
    """
    Move a file.
    """

    try:
        shutil.move(source, destination)

        return "File moved successfully."

    except Exception as e:
        return str(e)


@function_tool()
async def delete_file(context: RunContext, file_path: str) -> str:
    """
    Delete a file.
    """

    try:
        path = Path(file_path)

        if not path.exists():
            return "File not found."

        path.unlink()

        return "File deleted."

    except Exception as e:
        return str(e)
