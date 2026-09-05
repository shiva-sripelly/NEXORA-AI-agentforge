from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mcp import MCPConnection, MCPConnectionStatus, MCPTool


class MCPRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def connections(self, user_id: UUID):
        return list((await self.db.scalars(select(MCPConnection).where(MCPConnection.user_id == user_id).order_by(MCPConnection.created_at))).all())

    async def connection(self, connection_id: UUID, user_id: UUID):
        return await self.db.scalar(select(MCPConnection).where(MCPConnection.id == connection_id, MCPConnection.user_id == user_id))

    async def duplicate(self, user_id: UUID, server_type: str):
        return await self.db.scalar(select(MCPConnection).where(MCPConnection.user_id == user_id, MCPConnection.server_type == server_type))

    async def tools(self, user_id: UUID, enabled_only: bool = False):
        query = select(MCPTool).options(selectinload(MCPTool.connection)).join(MCPConnection).where(MCPConnection.user_id == user_id)
        if enabled_only:
            query = query.where(MCPConnection.is_enabled.is_(True), MCPConnection.status == MCPConnectionStatus.connected, MCPTool.is_enabled.is_(True))
        return list((await self.db.scalars(query.order_by(MCPTool.display_name))).all())

    async def tool(self, tool_id: UUID, user_id: UUID):
        return await self.db.scalar(select(MCPTool).options(selectinload(MCPTool.connection)).join(MCPConnection).where(MCPTool.id == tool_id, MCPConnection.user_id == user_id))

    async def sync_tools(self, connection: MCPConnection, discovered):
        existing = {tool.external_name: tool for tool in connection.tools}
        seen = set()
        for item in discovered:
            seen.add(item.name)
            tool = existing.get(item.name)
            if tool:
                tool.description = item.description
                tool.input_schema = item.input_schema
                tool.discovered_at = func.now()
            else:
                risk = "medium" if item.name == "read_text_file" else "low"
                tool = MCPTool(connection_id=connection.id, external_name=item.name,
                    display_name=item.name.replace("_", " ").title(), description=item.description,
                    input_schema=item.input_schema, risk_level=risk, requires_approval=False)
                self.db.add(tool)
        for name, tool in existing.items():
            if name not in seen:
                tool.is_enabled = False
        await self.db.flush()
        return await self.tools(connection.user_id)
