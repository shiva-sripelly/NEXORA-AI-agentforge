from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import or_, select

from app.core.config import settings
from app.models.mcp import AuditLog, MCPTool, ToolPermissionPolicy


DecisionName = Literal["allow", "require_approval", "deny"]
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
APPROVAL_MODES = {"never", "always", "risk_based"}
SENSITIVE_KEYS = {"authorization", "api_key", "apikey", "cookie", "credential", "password",
    "secret", "token", "access_token", "refresh_token", "private_key"}


def normalize_risk(value: str | None) -> str:
    risk = str(value or "low").casefold()
    return risk if risk in RISK_ORDER else "critical"


def sanitize_arguments(value: Any, key: str = "") -> Any:
    """Create an audit/display snapshot without persisting obvious credentials."""
    if key.casefold() in SENSITIVE_KEYS or any(part in key.casefold() for part in ("password", "secret", "token", "key")):
        return "[REDACTED]"
    if key.casefold() in {"text", "content", "body"} and isinstance(value, str):
        return f"[TEXT {len(value)} characters]"
    if isinstance(value, dict):
        return {str(child_key)[:120]: sanitize_arguments(child, str(child_key))
            for child_key, child in list(value.items())[:100]}
    if isinstance(value, list):
        return [sanitize_arguments(child) for child in value[:100]]
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


@dataclass(frozen=True)
class PolicyDecision:
    decision: DecisionName
    reason: str
    risk_level: str
    matched_policy: str
    requires_approval: bool
    approval_mode: str


class GovernanceService:
    def __init__(self, db):
        self.db = db

    async def evaluate_tool_execution(self, user, tool: MCPTool, arguments: dict,
            context: dict | None = None, *, audit: bool = True) -> PolicyDecision:
        risk = normalize_risk(tool.risk_level)
        policy = await self._matched_policy(user, tool.id)
        matched = f"policy:{policy.id}" if policy else "tool_default"
        mode = (policy.approval_mode if policy and policy.approval_mode else
            ("always" if tool.requires_approval else tool.approval_mode or "never"))
        mode = mode if mode in APPROVAL_MODES else "risk_based"

        if not tool.connection.is_enabled:
            decision = PolicyDecision("deny", "The MCP connection is disabled.", risk, matched, False, mode)
        elif not tool.is_enabled:
            decision = PolicyDecision("deny", "The MCP tool is disabled.", risk, matched, False, mode)
        elif tool.connection.transport != "stdio" or tool.connection.server_type not in {"analytics", "file"}:
            decision = PolicyDecision("deny", "This MCP connection is not permitted for execution.", risk, matched, False, mode)
        elif policy and policy.effect == "deny":
            decision = PolicyDecision("deny", "A governance policy denies this tool for the current user.", risk,
                matched, False, mode)
        elif mode == "always":
            decision = PolicyDecision("require_approval", self._approval_reason(tool, risk), risk, matched, True, mode)
        elif risk == "critical":
            decision = PolicyDecision("require_approval", "Critical-risk tools always require human approval.", risk,
                matched, True, mode)
        elif mode == "risk_based" and RISK_ORDER[risk] >= RISK_ORDER[normalize_risk(settings.tool_approval_risk_threshold)]:
            decision = PolicyDecision("require_approval", self._approval_reason(tool, risk), risk, matched, True, mode)
        else:
            decision = PolicyDecision("allow", "Governance policy allows this tool execution.", risk, matched, False, mode)

        if audit:
            await self.record_event(user.id, "tool_policy_evaluated", tool_id=tool.id,
                agent_run_id=(context or {}).get("agent_run_id"), metadata={
                    "decision": decision.decision, "reason": decision.reason, "risk_level": risk,
                    "matched_policy": matched, "approval_mode": mode,
                    "arguments": sanitize_arguments(arguments),
                })
        return decision

    async def _matched_policy(self, user, tool_id: UUID) -> ToolPermissionPolicy | None:
        role = user.role.value if hasattr(user.role, "value") else str(user.role)
        rows = list((await self.db.scalars(select(ToolPermissionPolicy).where(
            ToolPermissionPolicy.tool_id == tool_id,
            or_(ToolPermissionPolicy.user_id == user.id, ToolPermissionPolicy.role == role,
                (ToolPermissionPolicy.user_id.is_(None) & ToolPermissionPolicy.role.is_(None)))))).all())
        for predicate in (
            lambda item: item.user_id == user.id,
            lambda item: item.user_id is None and item.role == role,
            lambda item: item.user_id is None and item.role is None,
        ):
            matches = [item for item in rows if predicate(item)]
            if matches:
                return sorted(matches, key=lambda item: (item.effect != "deny", str(item.id)))[0]
        return None

    async def record_event(self, actor_user_id, event_type: str, *, tool_id=None, agent_run_id=None,
            approval_request_id=None, metadata: dict | None = None):
        event = AuditLog(actor_user_id=actor_user_id, event_type=event_type, tool_id=tool_id,
            agent_run_id=agent_run_id, approval_request_id=approval_request_id,
            metadata_json=sanitize_arguments(metadata or {}))
        self.db.add(event)
        await self.db.flush()
        return event

    @staticmethod
    def _approval_reason(tool: MCPTool, risk: str) -> str:
        if tool.external_name == "read_text_file":
            return "This tool requires human approval before accessing workspace files."
        return f"This {risk}-risk tool requires human approval before execution."
