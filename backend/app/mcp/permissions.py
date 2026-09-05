from fastapi import HTTPException


def require_executable(tool):
    connection = tool.connection
    if not connection.is_enabled:
        raise HTTPException(409, {"code": "MCP_CONNECTION_DISABLED", "message": "MCP connection is disabled."})
    if not tool.is_enabled:
        raise HTTPException(409, {"code": "MCP_TOOL_DISABLED", "message": "MCP tool is disabled."})
    if connection.transport != "stdio" or connection.server_type not in {"analytics", "file"}:
        raise HTTPException(403, {"code": "MCP_PERMISSION_DENIED", "message": "This connection cannot be executed."})
