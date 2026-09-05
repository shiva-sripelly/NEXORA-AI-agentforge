import asyncio
import json
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import settings
from app.mcp.schemas import DiscoveredTool, MCPError, MCPResult
from app.mcp.transport import child_environment


class MCPClient:
    def __init__(self, command: str, args: list[str], env: dict[str, str] | None = None):
        self.parameters = StdioServerParameters(command=command, args=args, env=child_environment(env or {}))
        self._transport = None
        self._session_context = None
        self.session: ClientSession | None = None

    async def connect(self):
        try:
            async with asyncio.timeout(settings.mcp_timeout_seconds):
                self._transport = stdio_client(self.parameters)
                read, write = await self._transport.__aenter__()
                self._session_context = ClientSession(read, write)
                self.session = await self._session_context.__aenter__()
                await self.session.initialize()
        except Exception as exc:
            await self.close()
            raise MCPError("MCP_CONNECTION_FAILED", "Unable to connect to MCP server") from exc
        return self

    async def list_tools(self) -> list[DiscoveredTool]:
        if not self.session:
            raise MCPError("MCP_CONNECTION_FAILED", "MCP client is not connected")
        try:
            async with asyncio.timeout(settings.mcp_timeout_seconds):
                result = await self.session.list_tools()
            return [DiscoveredTool(tool.name, tool.description, dict(tool.inputSchema or {})) for tool in result.tools]
        except Exception as exc:
            raise MCPError("MCP_CONNECTION_FAILED", "Unable to discover MCP tools") from exc

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPResult:
        if not self.session:
            raise MCPError("MCP_CONNECTION_FAILED", "MCP client is not connected")
        try:
            async with asyncio.timeout(settings.mcp_timeout_seconds):
                result = await self.session.call_tool(name, arguments)
            structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
            if structured is None:
                texts = [getattr(item, "text", "") for item in result.content if getattr(item, "type", None) == "text"]
                raw = "\n".join(texts)
                try:
                    structured = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    structured = {"content": raw}
            return MCPResult(data=structured if isinstance(structured, dict) else {"value": structured}, is_error=bool(result.isError))
        except MCPError:
            raise
        except Exception as exc:
            raise MCPError("MCP_TOOL_EXECUTION_FAILED", "MCP tool execution failed") from exc

    async def close(self):
        try:
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
            if self._transport:
                await self._transport.__aexit__(None, None, None)
        except Exception:
            pass
        finally:
            self.session = None
            self._session_context = None
            self._transport = None

    async def __aenter__(self):
        return await self.connect()

    async def __aexit__(self, *_):
        await self.close()
