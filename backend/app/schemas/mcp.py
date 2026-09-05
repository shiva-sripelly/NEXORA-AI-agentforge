from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConnectionCreate(BaseModel):
    server_type: Literal["analytics", "file"]
    name: str | None = Field(None, min_length=1, max_length=120)
    model_config = ConfigDict(extra="forbid")


class ConnectionOut(BaseModel):
    id: UUID; name: str; server_type: str; transport: str; status: str; is_enabled: bool; created_at: datetime; updated_at: datetime


class ToolUpdate(BaseModel):
    is_enabled: bool | None = None
    requires_approval: bool | None = None
    model_config = ConfigDict(extra="forbid")


class ToolOut(BaseModel):
    id: UUID; connection_id: UUID; connection_name: str; external_name: str; display_name: str
    description: str | None; input_schema: dict[str, Any]; is_enabled: bool
    requires_approval: bool; risk_level: str; discovered_at: datetime; updated_at: datetime


class ToolExecute(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")


class ToolCallOut(BaseModel):
    id: UUID; conversation_id: UUID | None; message_id: UUID | None; mcp_tool_id: UUID
    tool_name: str; status: str; arguments_summary: dict[str, Any]
    result_summary: str | None; error_message: str | None; started_at: datetime
    completed_at: datetime | None; created_at: datetime; approval_id: UUID | None = None
    final_message_content: str | None = None
    model_config = ConfigDict(from_attributes=True)


class ApprovalOut(BaseModel):
    id: UUID; tool_call_id: UUID; tool_name: str; status: str; risk_level: str
    arguments_summary: dict[str, Any]; requested_at: datetime; resolved_at: datetime | None
