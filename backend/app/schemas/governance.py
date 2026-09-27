from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class GovernanceToolUpdate(BaseModel):
    is_enabled: bool | None = None
    risk_level: Literal["low", "medium", "high", "critical"] | None = None
    approval_mode: Literal["never", "always", "risk_based"] | None = None
    model_config = ConfigDict(extra="forbid")


class PolicyCreate(BaseModel):
    tool_id: UUID
    user_id: UUID | None = None
    role: Literal["USER", "ADMIN"] | None = None
    effect: Literal["allow", "deny"]
    approval_mode: Literal["never", "always", "risk_based"] | None = None
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def one_subject_type(self):
        if self.user_id is not None and self.role is not None:
            raise ValueError("A policy may target a user or a role, not both")
        return self


class PolicyUpdate(BaseModel):
    effect: Literal["allow", "deny"] | None = None
    approval_mode: Literal["never", "always", "risk_based"] | None = None
    model_config = ConfigDict(extra="forbid")


class PolicyOut(BaseModel):
    id: UUID; tool_id: UUID; tool_name: str; user_id: UUID | None; role: str | None
    effect: str; approval_mode: str | None; created_at: datetime; updated_at: datetime


class AuditOut(BaseModel):
    id: UUID; actor_user_id: UUID | None; event_type: str; tool_id: UUID | None
    agent_run_id: UUID | None; approval_request_id: UUID | None
    metadata: dict; created_at: datetime
