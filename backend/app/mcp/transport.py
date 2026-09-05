import os
import sys
from pathlib import Path

from app.core.config import settings
from app.mcp.schemas import MCPError

SERVER_DEFINITIONS = {
    "analytics": {"name": "Analytics", "script": "analytics_server/server.py"},
    "file": {"name": "Files", "script": "file_server/server.py"},
}


def local_server_config(server_type: str) -> tuple[str, list[str], dict[str, str]]:
    definition = SERVER_DEFINITIONS.get(server_type)
    if not definition:
        raise MCPError("MCP_PERMISSION_DENIED", "Unsupported MCP server type")
    root = Path(settings.mcp_server_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    script = (root / definition["script"]).resolve()
    if not script.is_file():
        raise MCPError("MCP_CONNECTION_FAILED", "MCP server is unavailable")
    env = {"MCP_FILE_ROOT": str(Path(settings.mcp_file_root).resolve())} if server_type == "file" else {}
    return sys.executable, [str(script)], env


def safe_connection_values(server_type: str) -> dict:
    command, args, _ = local_server_config(server_type)
    return {"server_type": server_type, "transport": "stdio", "command": command, "args": args, "endpoint": None}


def child_environment(extra: dict[str, str]) -> dict[str, str]:
    allowed = {key: value for key, value in os.environ.items() if key in {"PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
    return {**allowed, **extra}
