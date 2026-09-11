from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class AgentState:
    run_id: UUID
    user_id: UUID
    conversation_id: UUID | None
    goal: str
    current_step: int
    max_steps: int
    available_tools: list[dict[str, Any]] = field(default_factory=list)
    selected_documents: list[UUID] = field(default_factory=list)
    completed_steps: list[int] = field(default_factory=list)
    previous_results: dict[int, dict[str, Any]] = field(default_factory=dict)
    status: str = "planning"
