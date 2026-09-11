from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentRunCreate(BaseModel):
    conversation_id: UUID
    goal: str = Field(min_length=1, max_length=10000)
    document_ids: list[UUID] = Field(default_factory=list, max_length=20)
    model_config = ConfigDict(extra="forbid")


class PlannedStep(BaseModel):
    step_number: int = Field(ge=1)
    step_type: Literal["tool", "rag", "final"] = Field(alias="type")
    title: str = Field(min_length=1, max_length=180)
    description: str | None = Field(None, max_length=1000)
    tool_name: str | None = Field(None, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def valid_shape(self):
        if self.step_type == "tool" and not self.tool_name:
            raise ValueError("Tool steps require tool_name")
        if self.step_type != "tool" and (self.tool_name or self.arguments):
            raise ValueError("Only tool steps may contain a tool or arguments")
        return self


class ExecutionPlan(BaseModel):
    goal: str = Field(min_length=1, max_length=10000)
    steps: list[PlannedStep] = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


class AgentStepOut(BaseModel):
    id: UUID
    step_number: int
    step_type: str
    title: str
    description: str | None
    tool_name: str | None
    arguments_summary: dict[str, Any]
    status: str
    result_summary: str | None
    error_message: str | None
    approval_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None


class AgentRunOut(BaseModel):
    id: UUID
    conversation_id: UUID | None
    triggering_message_id: UUID | None
    goal: str
    status: str
    current_step: int
    total_steps: int
    max_steps: int
    started_at: datetime
    completed_at: datetime | None
    failed_at: datetime | None
    error_message: str | None
    final_answer: str | None
    created_at: datetime
    updated_at: datetime
    steps: list[AgentStepOut] = Field(default_factory=list)
