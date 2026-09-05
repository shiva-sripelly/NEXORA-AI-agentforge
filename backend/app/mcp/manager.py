import logging

from app.mcp.client import MCPClient
from app.mcp.schemas import MCPError
from app.mcp.transport import local_server_config

log = logging.getLogger(__name__)


class MCPManager:
    def client_for(self, connection) -> MCPClient:
        command, args, env = local_server_config(connection.server_type)
        # Persisted command/args are audit information only. Execution always uses the whitelist.
        return MCPClient(command, args, env)

    async def discover(self, connection):
        async with self.client_for(connection) as client:
            return await client.list_tools()

    async def execute(self, connection, name: str, arguments: dict):
        async with self.client_for(connection) as client:
            available = {tool.name for tool in await client.list_tools()}
            if name not in available:
                raise MCPError("MCP_TOOL_NOT_FOUND", "MCP tool is unavailable")
            result = await client.call_tool(name, arguments)
            if result.is_error:
                raise MCPError("MCP_TOOL_EXECUTION_FAILED", "MCP tool reported an error")
            return result.data
