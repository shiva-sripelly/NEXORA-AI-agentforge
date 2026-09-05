import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class MCPConnectionStatus(str, enum.Enum):
    connected = "connected"
    disconnected = "disconnected"
    error = "error"


class ToolCallStatus(str, enum.Enum):
    pending = "pending"
    awaiting_approval = "awaiting_approval"
    running = "running"
    completed = "completed"
    failed = "failed"
    denied = "denied"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    denied = "denied"


class MCPConnection(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "mcp_connections"
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    server_type: Mapped[str] = mapped_column(String(40))
    transport: Mapped[str] = mapped_column(String(20), default="stdio")
    command: Mapped[str | None] = mapped_column(String(255), nullable=True)
    args: Mapped[list | None] = mapped_column(JSON, nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[MCPConnectionStatus] = mapped_column(Enum(MCPConnectionStatus, name="mcp_connection_status"), default=MCPConnectionStatus.disconnected)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    tools = relationship("MCPTool", back_populates="connection", cascade="all, delete-orphan", lazy="selectin")


class MCPTool(UUIDMixin, Base):
    __tablename__ = "mcp_tools"
    __table_args__ = (UniqueConstraint("connection_id", "external_name"),)
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("mcp_connections.id", ondelete="CASCADE"), index=True)
    external_name: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    connection = relationship("MCPConnection", back_populates="tools")


class ToolCall(UUIDMixin, Base):
    __tablename__ = "tool_calls"
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    message_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    mcp_tool_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("mcp_tools.id", ondelete="CASCADE"))
    tool_name: Mapped[str] = mapped_column(String(120))
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[ToolCallStatus] = mapped_column(Enum(ToolCallStatus, name="tool_call_status"), default=ToolCallStatus.pending)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tool = relationship("MCPTool", lazy="selectin")
    approval = relationship("ApprovalRequest", back_populates="tool_call", uselist=False, cascade="all, delete-orphan", lazy="selectin")

    @property
    def arguments_summary(self):
        summary = {}
        for key, value in self.arguments.items():
            if isinstance(value, list): summary[f"{key}_count"] = len(value)
            elif key == "path": summary[key] = str(value)[:160]
            elif isinstance(value, str): summary[f"{key}_characters"] = len(value)
            elif isinstance(value, (int, float, bool)): summary[key] = value
        return summary

    @property
    def result_summary(self):
        if self.result is None: return None
        if self.tool_name == "calculate_statistics":
            return ", ".join(f"{key}: {self.result.get(key)}" for key in ("count", "sum", "mean", "min", "max", "median"))
        return {"analyze_text": "Text analysis completed.", "list_files": "Workspace files listed.",
            "read_text_file": "Workspace text file read.", "file_metadata": "File metadata read."}.get(self.tool_name, "Tool completed successfully.")

    @property
    def approval_id(self):
        return self.approval.id if self.approval else None


class ApprovalRequest(UUIDMixin, Base):
    __tablename__ = "approval_requests"
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tool_call_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tool_calls.id", ondelete="CASCADE"), unique=True)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus, name="approval_status"), default=ApprovalStatus.pending)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    tool_call = relationship("ToolCall", back_populates="approval")
