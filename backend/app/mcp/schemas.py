from dataclasses import dataclass
from typing import Any


@dataclass
class DiscoveredTool:
    name: str
    description: str | None
    input_schema: dict[str, Any]


@dataclass
class MCPResult:
    data: dict[str, Any]
    is_error: bool = False


class MCPError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
