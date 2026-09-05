import os
from pathlib import Path, PureWindowsPath

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AgentForge Files")
ROOT = Path(os.environ.get("MCP_FILE_ROOT", "storage/mcp_workspace")).resolve()
MAX_READ_BYTES = 1_000_000


def safe_path(value: str) -> Path:
    candidate = Path(value)
    windows = PureWindowsPath(value)
    parts = [part for part in (*candidate.parts, *windows.parts) if part not in {".", "", "\\", "/"}]
    if candidate.is_absolute() or windows.is_absolute() or windows.drive or ".." in parts or any(part.startswith(".") for part in parts):
        raise ValueError("Path is outside the allowed workspace")
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("Path is outside the allowed workspace") from exc
    return resolved


@mcp.tool()
def list_files(path: str = ".") -> dict:
    """List files and directories inside the configured AgentForge workspace."""
    target = safe_path(path)
    if not target.is_dir():
        raise ValueError("Directory not found")
    items = []
    for item in sorted(target.iterdir(), key=lambda entry: entry.name.casefold())[:500]:
        if item.name.startswith("."):
            continue
        resolved = item.resolve()
        try:
            resolved.relative_to(ROOT)
        except ValueError:
            continue
        items.append({"name": item.name, "type": "directory" if item.is_dir() else "file"})
    return {"path": path, "items": items}


@mcp.tool()
def read_text_file(path: str) -> dict:
    """Read a UTF-8 text file inside the configured AgentForge workspace."""
    target = safe_path(path)
    if not target.is_file():
        raise ValueError("File not found")
    if target.stat().st_size > MAX_READ_BYTES:
        raise ValueError("File is too large")
    return {"path": path, "content": target.read_text(encoding="utf-8")}


@mcp.tool()
def file_metadata(path: str) -> dict:
    """Return basic metadata for a workspace file without reading it."""
    target = safe_path(path)
    if not target.exists():
        raise ValueError("Path not found")
    stat = target.stat()
    return {"path": path, "type": "directory" if target.is_dir() else "file", "size": stat.st_size}


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    mcp.run(transport="stdio")
