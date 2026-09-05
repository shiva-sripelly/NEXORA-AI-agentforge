import logging

from fastapi import HTTPException

from app.mcp.manager import MCPManager
from app.mcp.schemas import MCPError
from app.mcp.transport import SERVER_DEFINITIONS, safe_connection_values
from app.models.mcp import MCPConnection, MCPConnectionStatus
from app.repositories.mcp_repository import MCPRepository

log = logging.getLogger(__name__)


class MCPService:
    def __init__(self, db):
        self.db, self.repo, self.manager = db, MCPRepository(db), MCPManager()

    async def require_connection(self, connection_id, user_id):
        item = await self.repo.connection(connection_id, user_id)
        if not item:
            raise HTTPException(404, {"code": "MCP_CONNECTION_NOT_FOUND", "message": "MCP connection not found."})
        return item

    async def create(self, user, server_type: str, name: str | None):
        if server_type not in SERVER_DEFINITIONS:
            raise HTTPException(422, {"code": "MCP_INVALID_SERVER_TYPE", "message": "Choose Analytics or Files."})
        if await self.repo.duplicate(user.id, server_type):
            raise HTTPException(409, {"code": "MCP_CONNECTION_EXISTS", "message": "This MCP server is already registered."})
        values = safe_connection_values(server_type)
        clean_name = (name or SERVER_DEFINITIONS[server_type]["name"]).strip()[:120] or SERVER_DEFINITIONS[server_type]["name"]
        item = MCPConnection(user_id=user.id, name=clean_name,
            status=MCPConnectionStatus.disconnected, is_enabled=True, **values)
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        log.info("mcp_connection_created user_id=%s connection_id=%s type=%s", user.id, item.id, server_type)
        return item

    async def refresh(self, item):
        if not item.is_enabled:
            raise HTTPException(409, {"code": "MCP_CONNECTION_DISABLED", "message": "MCP connection is disabled."})
        try:
            discovered = await self.manager.discover(item)
            item.status = MCPConnectionStatus.connected
            await self.repo.sync_tools(item, discovered)
            await self.db.commit()
            log.info("mcp_tools_discovered connection_id=%s count=%s", item.id, len(discovered))
            return await self.repo.tools(item.user_id)
        except MCPError as exc:
            item.status = MCPConnectionStatus.error
            await self.db.commit()
            log.warning("mcp_connection_failed connection_id=%s code=%s", item.id, exc.code)
            raise HTTPException(503, {"code": exc.code, "message": str(exc)}) from exc
