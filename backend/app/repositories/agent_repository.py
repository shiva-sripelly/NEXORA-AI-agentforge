from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import AgentRun, AgentStep
from app.models.mcp import ToolCall


class AgentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _detail(self):
        return (selectinload(AgentRun.steps).selectinload(AgentStep.tool),
            selectinload(AgentRun.steps).selectinload(AgentStep.tool_call).selectinload(ToolCall.approval))

    async def list(self, user_id: UUID, conversation_id: UUID | None = None, limit: int = 100):
        query = select(AgentRun).options(*self._detail()).where(AgentRun.user_id == user_id)
        if conversation_id:
            query = query.where(AgentRun.conversation_id == conversation_id)
        return list((await self.db.scalars(query.order_by(AgentRun.created_at.desc()).limit(limit))).unique().all())

    async def owned(self, run_id: UUID, user_id: UUID, lock: bool = False):
        query = (select(AgentRun).options(*self._detail()).where(AgentRun.id == run_id,
            AgentRun.user_id == user_id).execution_options(populate_existing=True))
        if lock:
            query = query.with_for_update()
        return await self.db.scalar(query)

    async def step_for_tool_call(self, tool_call_id: UUID, user_id: UUID):
        query = (select(AgentStep).join(AgentRun).options(selectinload(AgentStep.run).selectinload(AgentRun.steps),
            selectinload(AgentStep.tool_call).selectinload(ToolCall.approval))
            .where(AgentStep.tool_call_id == tool_call_id, AgentRun.user_id == user_id))
        return await self.db.scalar(query)
