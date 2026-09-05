from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mcp import ApprovalRequest, MCPTool, ToolCall


class ApprovalRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, user_id: UUID, pending_only: bool = False):
        query = select(ApprovalRequest).options(selectinload(ApprovalRequest.tool_call).selectinload(ToolCall.tool).selectinload(MCPTool.connection)).where(ApprovalRequest.user_id == user_id)
        if pending_only:
            query = query.where(ApprovalRequest.status == "pending")
        return list((await self.db.scalars(query.order_by(ApprovalRequest.requested_at.desc()))).all())

    async def owned(self, approval_id: UUID, user_id: UUID):
        query = select(ApprovalRequest).options(selectinload(ApprovalRequest.tool_call).selectinload(ToolCall.tool).selectinload(MCPTool.connection)).where(ApprovalRequest.id == approval_id, ApprovalRequest.user_id == user_id)
        return await self.db.scalar(query)
