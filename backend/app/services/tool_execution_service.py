import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jsonschema import ValidationError, validate

from app.mcp.manager import MCPManager
from app.mcp.schemas import MCPError
from app.models.mcp import ApprovalRequest, ApprovalStatus, MCPConnectionStatus, ToolCall, ToolCallStatus
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.mcp_repository import MCPRepository
from app.repositories.tool_call_repository import ToolCallRepository
from app.ai.llm.base import LLMToolCall
from app.ai.llm.factory import llm_factory
from app.ai.prompts import DEFAULT_SYSTEM_PROMPT
from app.models.agent import AgentRunStatus, AgentStepStatus
from app.models.conversation import Message
from app.repositories.agent_repository import AgentRepository
from app.services.conversation_service import ConversationService
from app.services.governance_service import GovernanceService, sanitize_arguments
from app.core.config import settings

log = logging.getLogger(__name__)


def arguments_summary(arguments: dict) -> dict:
    summary = {}
    for key, value in arguments.items():
        if isinstance(value, list): summary[f"{key}_count"] = len(value)
        elif key == "path": summary[key] = str(value)[:160]
        elif isinstance(value, str): summary[f"{key}_characters"] = len(value)
        elif isinstance(value, (int, float, bool)): summary[key] = value
    return summary


def result_summary(name: str, result: dict | None) -> str | None:
    if result is None: return None
    if name == "calculate_statistics":
        return ", ".join(f"{key}: {result.get(key)}" for key in ("count", "sum", "mean", "min", "max", "median"))
    if name == "analyze_text": return "Text analysis completed."
    if name == "list_files": return f"Listed {len(result.get('items', []))} workspace items."
    if name == "read_text_file": return "Read the requested workspace text file."
    return "Tool completed successfully."


class ToolExecutionService:
    def __init__(self, db):
        self.db, self.tools, self.calls, self.approvals = db, MCPRepository(db), ToolCallRepository(db), ApprovalRepository(db)
        self.manager = MCPManager()
        self.governance = GovernanceService(db)

    async def execute(self, user, tool_id, arguments, conversation_id=None, agent_run_id=None):
        tool = await self.tools.tool(tool_id, user.id)
        if not tool:
            raise HTTPException(404, {"code": "MCP_TOOL_NOT_FOUND", "message": "MCP tool not found."})
        try: validate(instance=arguments, schema=tool.input_schema)
        except ValidationError as exc:
            raise HTTPException(422, {"code": "MCP_INVALID_ARGUMENTS", "message": "Tool arguments do not match its schema."}) from exc
        decision = await self.governance.evaluate_tool_execution(user, tool, arguments,
            {"agent_run_id": agent_run_id})
        if decision.decision == "deny":
            await self.governance.record_event(user.id, "tool_execution_denied", tool_id=tool.id,
                agent_run_id=agent_run_id, metadata={"reason": decision.reason, "risk_level": decision.risk_level})
            await self.db.commit()
            raise HTTPException(403, {"code": "MCP_POLICY_DENIED", "message": decision.reason})
        call = ToolCall(user_id=user.id, conversation_id=conversation_id, mcp_tool_id=tool.id,
            tool_name=tool.external_name, arguments=arguments, status=ToolCallStatus.pending)
        call.approval = None
        self.db.add(call)
        await self.db.flush()
        if decision.requires_approval:
            call.status = ToolCallStatus.awaiting_approval
            call.approval = ApprovalRequest(user_id=user.id, tool_call_id=call.id, agent_run_id=agent_run_id,
                status=ApprovalStatus.pending, reason=decision.reason, risk_level=decision.risk_level,
                tool_name_snapshot=tool.external_name, tool_arguments=sanitize_arguments(arguments),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.approval_expiry_minutes))
            self.db.add(call.approval)
            await self.db.flush()
            await self.governance.record_event(user.id, "approval_requested", tool_id=tool.id,
                agent_run_id=agent_run_id, approval_request_id=call.approval.id,
                metadata={"reason": decision.reason, "risk_level": decision.risk_level})
            await self.db.commit()
            await self.db.refresh(call)
            log.info("mcp_approval_requested user_id=%s tool_call_id=%s", user.id, call.id)
            return call
        await self.governance.record_event(user.id, "tool_execution_allowed", tool_id=tool.id,
            agent_run_id=agent_run_id, metadata={"risk_level": decision.risk_level})
        await self._run(call, tool)
        return call

    async def _run(self, call, tool, commit_running=True):
        call.status = ToolCallStatus.running
        if commit_running:
            await self.db.commit()
        else:
            await self.db.flush()
        try:
            call.result = await self.manager.execute(tool.connection, tool.external_name, call.arguments)
            tool.connection.status = MCPConnectionStatus.connected
            call.status = ToolCallStatus.completed
            call.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(call)
            log.info("mcp_tool_completed tool_call_id=%s tool=%s", call.id, tool.external_name)
        except MCPError as exc:
            call.status = ToolCallStatus.failed
            tool.connection.status = MCPConnectionStatus.error
            call.error_message = "Tool execution failed."
            call.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            log.warning("mcp_tool_failed tool_call_id=%s code=%s", call.id, exc.code)
            raise HTTPException(502, {"code": exc.code, "message": str(exc)}) from exc

    async def resolve(self, user, approval_id, approve: bool, resolution_note: str | None = None):
        approval = await self.approvals.owned(approval_id, user.id)
        if not approval:
            raise HTTPException(404, {"code": "MCP_APPROVAL_NOT_FOUND", "message": "Approval request not found."})
        agent_step = await AgentRepository(self.db).step_for_tool_call(approval.tool_call_id, user.id)
        if agent_step:
            run = await AgentRepository(self.db).owned(agent_step.agent_run_id, user.id, lock=True)
            approval = await self.approvals.owned(approval_id, user.id, lock=True)
            agent_step = next((step for step in run.steps if step.tool_call_id == approval.tool_call_id), None)
            terminal = {AgentRunStatus.completed, AgentRunStatus.failed, AgentRunStatus.cancelled,
                AgentRunStatus.max_steps_reached}
            if (run.status in terminal or run.status != AgentRunStatus.awaiting_approval
                    or not agent_step or agent_step.status != AgentStepStatus.awaiting_approval
                    or approval.tool_call.status != ToolCallStatus.awaiting_approval):
                raise HTTPException(409, {"code": "MCP_APPROVAL_STALE",
                    "message": "This approval is no longer valid for the agent run."})
        else:
            approval = await self.approvals.owned(approval_id, user.id, lock=True)
        if approval.status != ApprovalStatus.pending:
            raise HTTPException(409, {"code": "MCP_APPROVAL_RESOLVED", "message": "Approval request is already resolved."})
        if self._is_expired(approval):
            await self._expire(approval, agent_step)
            raise HTTPException(409, {"code": "MCP_APPROVAL_EXPIRED", "message": "Approval request has expired."})
        call = approval.tool_call
        try: validate(instance=call.arguments, schema=call.tool.input_schema)
        except ValidationError as exc:
            await self._invalidate(approval, agent_step, "Tool arguments are no longer valid.")
            raise HTTPException(409, {"code": "MCP_APPROVAL_STALE", "message": "Tool arguments are no longer valid."}) from exc
        if approve:
            decision = await self.governance.evaluate_tool_execution(user, call.tool, call.arguments,
                {"agent_run_id": approval.agent_run_id})
            if decision.decision == "deny":
                await self._invalidate(approval, agent_step, decision.reason)
                raise HTTPException(409, {"code": "MCP_APPROVAL_STALE", "message": decision.reason})
        approval.status = ApprovalStatus.approved if approve else ApprovalStatus.denied
        approval.resolved_at, approval.resolved_by = datetime.now(timezone.utc), user.id
        approval.resolution_note = resolution_note
        if not approve:
            call.status, call.completed_at = ToolCallStatus.denied, datetime.now(timezone.utc)
            await self.governance.record_event(user.id, "approval_denied", tool_id=call.mcp_tool_id,
                agent_run_id=approval.agent_run_id, approval_request_id=approval.id,
                metadata={"resolution_note": resolution_note})
            await self.db.commit()
            log.info("mcp_approval_denied user_id=%s tool_call_id=%s", user.id, call.id)
            return call
        await self.governance.record_event(user.id, "approval_approved", tool_id=call.mcp_tool_id,
            agent_run_id=approval.agent_run_id, approval_request_id=approval.id,
            metadata={"resolution_note": resolution_note})
        await self.governance.record_event(user.id, "tool_execution_allowed", tool_id=call.mcp_tool_id,
            agent_run_id=approval.agent_run_id, approval_request_id=approval.id,
            metadata={"risk_level": approval.risk_level})
        if agent_step:
            await self.db.flush()
            await self._run(call, call.tool, commit_running=False)
        else:
            await self.db.commit()
            await self._run(call, call.tool)
        log.info("mcp_approval_approved user_id=%s tool_call_id=%s", user.id, call.id)
        return call

    async def list_approvals(self, user_id, pending_only: bool = False):
        await self.expire_pending(user_id)
        return await self.approvals.list(user_id, pending_only)

    async def expire_pending(self, user_id=None):
        now = datetime.now(timezone.utc)
        expired = await self.approvals.expired_pending(now, user_id)
        for approval in expired:
            agent_step = await AgentRepository(self.db).step_for_tool_call(approval.tool_call_id, approval.user_id)
            await self._expire(approval, agent_step, commit=False)
        if expired:
            await self.db.commit()
        return len(expired)

    async def _expire(self, approval, agent_step=None, *, commit=True):
        approval.status = ApprovalStatus.expired
        approval.resolved_at = datetime.now(timezone.utc)
        approval.reason = approval.reason or "Approval expired before it was resolved."
        approval.tool_call.status = ToolCallStatus.failed
        approval.tool_call.error_message = "Approval request expired."
        approval.tool_call.completed_at = datetime.now(timezone.utc)
        await self._fail_waiting_agent(agent_step, "Approval request expired.")
        await self.governance.record_event(None, "approval_expired", tool_id=approval.tool_call.mcp_tool_id,
            agent_run_id=approval.agent_run_id, approval_request_id=approval.id)
        if commit:
            await self.db.commit()

    async def _invalidate(self, approval, agent_step, reason):
        approval.status = ApprovalStatus.cancelled
        approval.resolved_at = datetime.now(timezone.utc)
        approval.reason = reason[:500]
        approval.tool_call.status = ToolCallStatus.denied
        approval.tool_call.error_message = "Approval request is no longer valid."
        approval.tool_call.completed_at = datetime.now(timezone.utc)
        await self._fail_waiting_agent(agent_step, "Approval request is no longer valid.")
        await self.governance.record_event(None, "approval_cancelled", tool_id=approval.tool_call.mcp_tool_id,
            agent_run_id=approval.agent_run_id, approval_request_id=approval.id, metadata={"reason": reason})
        await self.db.commit()

    @staticmethod
    async def _fail_waiting_agent(agent_step, message):
        if not agent_step:
            return
        run = agent_step.run
        agent_step.status = AgentStepStatus.failed
        agent_step.error_message = message
        agent_step.completed_at = datetime.now(timezone.utc)
        run.status = AgentRunStatus.failed
        run.error_message = message
        run.failed_at = datetime.now(timezone.utc)
        for step in run.steps:
            if step.step_number > agent_step.step_number and step.status == AgentStepStatus.pending:
                step.status = AgentStepStatus.skipped

    @staticmethod
    def _is_expired(approval):
        if not approval.expires_at:
            return False
        expires_at = approval.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= datetime.now(timezone.utc)

    async def continue_approved_chat(self, user, call) -> str | None:
        if not call.conversation_id or not call.message_id or call.status != ToolCallStatus.completed:
            return None
        try:
            conversation = await ConversationService(self.db).require(call.conversation_id, user)
            history = await ConversationService(self.db).messages.recent(conversation.id, 20)
            prompt = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT +
                "\n\nAnswer from the executed tool result. Never invent tool output or reveal hidden reasoning or connection configuration."}]
            prompt += [{"role": message.role.value, "content": message.content} for message in history if message.id != call.message_id]
            provider = llm_factory.get_provider(conversation.model_provider)
            choice = LLMToolCall(id=str(call.id), name=call.tool_name, arguments=call.arguments)
            content = ""
            async for chunk in provider.stream_with_tool_result(prompt, conversation.model_name, choice, call.result or {}):
                content += chunk
            if content.strip():
                message = await self.db.get(Message, call.message_id)
                if message:
                    message.content = content
                    await self.db.commit()
                    return content
        except Exception:
            log.exception("mcp_approved_chat_continuation_failed tool_call_id=%s", call.id)
        return None
