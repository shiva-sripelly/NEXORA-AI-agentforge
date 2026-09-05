from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mcp import ToolCall


class ToolCallRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, user_id: UUID, limit: int = 100):
        query = select(ToolCall).options(selectinload(ToolCall.tool), selectinload(ToolCall.approval)).where(ToolCall.user_id == user_id).order_by(ToolCall.created_at.desc()).limit(limit)
        return list((await self.db.scalars(query)).all())

    async def owned(self, call_id: UUID, user_id: UUID):
        query = select(ToolCall).options(selectinload(ToolCall.tool), selectinload(ToolCall.approval)).where(ToolCall.id == call_id, ToolCall.user_id == user_id)
        return await self.db.scalar(query)
