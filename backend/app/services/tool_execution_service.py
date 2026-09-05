import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from jsonschema import ValidationError, validate

from app.mcp.manager import MCPManager
from app.mcp.permissions import require_executable
from app.mcp.schemas import MCPError
from app.models.mcp import ApprovalRequest, ApprovalStatus, MCPConnectionStatus, ToolCall, ToolCallStatus
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.mcp_repository import MCPRepository
from app.repositories.tool_call_repository import ToolCallRepository
from app.ai.llm.base import LLMToolCall
from app.ai.llm.factory import llm_factory
from app.ai.prompts import DEFAULT_SYSTEM_PROMPT
from app.models.conversation import Message
from app.services.conversation_service import ConversationService

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

    async def execute(self, user, tool_id, arguments, conversation_id=None, bypass_approval=False):
        tool = await self.tools.tool(tool_id, user.id)
        if not tool:
            raise HTTPException(404, {"code": "MCP_TOOL_NOT_FOUND", "message": "MCP tool not found."})
        require_executable(tool)
        try: validate(instance=arguments, schema=tool.input_schema)
        except ValidationError as exc:
            raise HTTPException(422, {"code": "MCP_INVALID_ARGUMENTS", "message": "Tool arguments do not match its schema."}) from exc
        call = ToolCall(user_id=user.id, conversation_id=conversation_id, mcp_tool_id=tool.id,
            tool_name=tool.external_name, arguments=arguments, status=ToolCallStatus.pending)
        call.approval = None
        self.db.add(call)
        await self.db.flush()
        if tool.requires_approval and not bypass_approval:
            call.status = ToolCallStatus.awaiting_approval
            call.approval = ApprovalRequest(user_id=user.id, tool_call_id=call.id, status=ApprovalStatus.pending)
            await self.db.commit()
            await self.db.refresh(call)
            log.info("mcp_approval_requested user_id=%s tool_call_id=%s", user.id, call.id)
            return call
        await self._run(call, tool)
        return call

    async def _run(self, call, tool):
        call.status = ToolCallStatus.running
        await self.db.commit()
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

    async def resolve(self, user, approval_id, approve: bool):
        approval = await self.approvals.owned(approval_id, user.id)
        if not approval:
            raise HTTPException(404, {"code": "MCP_APPROVAL_NOT_FOUND", "message": "Approval request not found."})
        if approval.status != ApprovalStatus.pending:
            raise HTTPException(409, {"code": "MCP_APPROVAL_RESOLVED", "message": "Approval request is already resolved."})
        if approve:
            require_executable(approval.tool_call.tool)
        approval.status = ApprovalStatus.approved if approve else ApprovalStatus.denied
        approval.resolved_at, approval.resolved_by = datetime.now(timezone.utc), user.id
        call = approval.tool_call
        if not approve:
            call.status, call.completed_at = ToolCallStatus.denied, datetime.now(timezone.utc)
            await self.db.commit()
            log.info("mcp_approval_denied user_id=%s tool_call_id=%s", user.id, call.id)
            return call
        await self.db.commit()
        await self._run(call, call.tool)
        log.info("mcp_approval_approved user_id=%s tool_call_id=%s", user.id, call.id)
        return call

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
