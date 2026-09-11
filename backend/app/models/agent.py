import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class AgentRunStatus(str, enum.Enum):
    planning = "planning"
    running = "running"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    max_steps_reached = "max_steps_reached"


class AgentStepType(str, enum.Enum):
    tool = "tool"
    rag = "rag"
    final = "final"


class AgentStepStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"
    cancelled = "cancelled"


class AgentRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    triggering_message_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[AgentRunStatus] = mapped_column(Enum(AgentRunStatus, name="agent_run_status"), default=AgentRunStatus.planning)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    max_steps: Mapped[int] = mapped_column(Integer)
    selected_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps = relationship("AgentStep", back_populates="run", cascade="all, delete-orphan", order_by="AgentStep.step_number", lazy="selectin")


class AgentStep(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agent_steps"
    __table_args__ = (UniqueConstraint("agent_run_id", "step_number"),)
    agent_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[AgentStepType] = mapped_column(Enum(AgentStepType, name="agent_step_type"))
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mcp_tool_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("mcp_tools.id", ondelete="SET NULL"), nullable=True)
    tool_call_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tool_calls.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    arguments: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[AgentStepStatus] = mapped_column(Enum(AgentStepStatus, name="agent_step_status"), default=AgentStepStatus.pending)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run = relationship("AgentRun", back_populates="steps")
    tool = relationship("MCPTool", lazy="selectin")
    tool_call = relationship("ToolCall", lazy="selectin")
