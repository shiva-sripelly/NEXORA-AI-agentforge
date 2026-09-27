from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.models.mcp import AuditLog, MCPConnection, MCPTool, ToolPermissionPolicy


class GovernanceRepository:
    def __init__(self, db):
        self.db = db

    async def tools(self):
        query = (select(MCPTool).options(selectinload(MCPTool.connection))
            .join(MCPConnection).order_by(MCPConnection.name, MCPTool.display_name))
        return list((await self.db.scalars(query)).all())

    async def tool(self, tool_id: UUID):
        return await self.db.scalar(select(MCPTool).options(selectinload(MCPTool.connection))
            .where(MCPTool.id == tool_id))

    async def policies(self):
        return list((await self.db.scalars(select(ToolPermissionPolicy)
            .options(selectinload(ToolPermissionPolicy.tool))
            .order_by(ToolPermissionPolicy.created_at.desc()))).all())

    async def policy(self, policy_id: UUID):
        return await self.db.scalar(select(ToolPermissionPolicy)
            .options(selectinload(ToolPermissionPolicy.tool)).where(ToolPermissionPolicy.id == policy_id))

    async def conflicting_policy(self, tool_id: UUID, user_id, role, exclude_id=None):
        subject = (ToolPermissionPolicy.user_id.is_(None) if user_id is None else ToolPermissionPolicy.user_id == user_id)
        role_subject = (ToolPermissionPolicy.role.is_(None) if role is None else ToolPermissionPolicy.role == role)
        query = select(ToolPermissionPolicy).where(ToolPermissionPolicy.tool_id == tool_id,
            and_(subject, role_subject))
        if exclude_id:
            query = query.where(ToolPermissionPolicy.id != exclude_id)
        return await self.db.scalar(query)

    async def audit(self, limit: int = 200):
        return list((await self.db.scalars(select(AuditLog)
            .order_by(AuditLog.created_at.desc()).limit(limit))).all())
