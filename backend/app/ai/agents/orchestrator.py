import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from jsonschema import ValidationError, validate
from sqlalchemy import select, update

from app.ai.agents.planner import AgentPlanError, AgentPlanner, PlanValidator
from app.ai.agents.references import StepReferenceError, resolve_references
from app.ai.agents.state import AgentState
from app.ai.llm.factory import llm_factory
from app.ai.rag.service import RAGService
from app.core.config import settings
from app.models.agent import AgentRun, AgentRunStatus, AgentStep, AgentStepStatus, AgentStepType
from app.models.conversation import MessageRole
from app.models.document import MessageSource
from app.models.mcp import ToolCall, ToolCallStatus
from app.repositories.agent_repository import AgentRepository
from app.repositories.conversation_repository import MessageRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.mcp_repository import MCPRepository
from app.schemas.agent import AgentRunCreate, ExecutionPlan, PlannedStep
from app.services.conversation_service import ConversationService
from app.services.tool_execution_service import ToolExecutionService, result_summary

log = logging.getLogger(__name__)
_active_runs: set[str] = set()


def now():
    return datetime.now(timezone.utc)


class AgentOrchestrator:
    def __init__(self, db, planner: AgentPlanner | None = None):
        self.db = db
        self.runs = AgentRepository(db)
        self.tools = MCPRepository(db)
        self.messages = MessageRepository(db)
        self.planner = planner or AgentPlanner()

    async def create_run(self, user, data: AgentRunCreate, emit=None):
        conversation = await ConversationService(self.db).require(data.conversation_id, user)
        documents = await DocumentRepository(self.db).validate_ready(data.document_ids, user.id) if data.document_ids else []
        if documents is None:
            raise HTTPException(404, "One or more documents were not found")
        message = await self.messages.create(conversation.id, MessageRole.user, data.goal)
        await ConversationService(self.db).title_first(conversation, data.goal)
        run = AgentRun(user_id=user.id, conversation_id=conversation.id, triggering_message_id=message.id,
            goal=data.goal, status=AgentRunStatus.planning, max_steps=settings.agent_max_steps,
            selected_document_ids=[str(item.id) for item in documents])
        self.db.add(run)
        await self.db.commit(); await self.db.refresh(run)
        log.info("agent_run_created user_id=%s run_id=%s", user.id, run.id)
        await self._emit(emit, "agent_run_started", {"run_id": str(run.id), "status": run.status.value})
        available = await self.tools.tools(user.id, enabled_only=True)
        tool_specs = [{"name": item.external_name, "description": item.description, "input_schema": item.input_schema} for item in available]
        document_specs = [{"id": str(item.id), "name": item.display_name} for item in documents]
        provider = llm_factory.get_provider(conversation.model_provider)
        require_tool = "tool" in data.goal.casefold().split()
        log.info("agent_planner_tools run_id=%s enabled_tools=%s", run.id,
            [item.external_name for item in available])
        try:
            try:
                plan = await self.planner.create_plan(provider, conversation.model_name, data.goal, tool_specs,
                    document_specs, settings.agent_max_steps, require_tool)
            except AgentPlanError:
                if settings.agent_max_replans <= 0:
                    raise
                plan = await self.planner.create_plan(provider, conversation.model_name, data.goal, tool_specs,
                    document_specs, settings.agent_max_steps, require_tool,
                    "The previous response did not match the required plan schema. Return only the exact JSON shape requested.")
            if require_tool and not any(step.step_type == "tool" for step in plan.steps):
                if settings.agent_max_replans <= 0:
                    raise AgentPlanError("The requested MCP tool is not enabled, connected, or selected by the planner.")
                plan = await self.planner.create_plan(provider, conversation.model_name, data.goal, tool_specs,
                    document_specs, settings.agent_max_steps, True,
                    "The previous plan omitted required tool execution. Select an appropriate enabled tool and end with a final step.")
            await self.db.refresh(run)
            if run.status == AgentRunStatus.cancelled:
                return await self.runs.owned(run.id, user.id)
            if documents and not any(step.step_type == "rag" for step in plan.steps):
                plan = ExecutionPlan(goal=plan.goal, steps=[PlannedStep(step_number=1, type="rag",
                    title="Retrieve selected knowledge")] + [step.model_copy(update={"step_number": step.step_number + 1})
                    for step in plan.steps])
            by_name = {item.external_name: item for item in available}
            PlanValidator().validate(plan, by_name, bool(documents), settings.agent_max_steps,
                settings.agent_max_tool_calls, require_tool)
            for planned in plan.steps:
                tool = by_name.get(planned.tool_name) if planned.tool_name else None
                self.db.add(AgentStep(run=run, step_number=planned.step_number,
                    step_type=AgentStepType(planned.step_type), title=planned.title, description=planned.description,
                    mcp_tool_id=tool.id if tool else None, arguments=planned.arguments or None,
                    status=AgentStepStatus.pending))
            run.total_steps = len(plan.steps)
            run.status = AgentRunStatus.running
            await self.db.commit()
            log.info("agent_plan_created run_id=%s steps=%s", run.id, run.total_steps)
            await self._emit(emit, "plan_created", {"run_id": str(run.id), "steps": [
                {"step_number": step.step_number, "title": step.title, "type": step.step_type,
                    "tool": step.tool_name} for step in plan.steps]})
        except asyncio.CancelledError:
            await self.db.refresh(run)
            if run.status != AgentRunStatus.cancelled:
                run.status = AgentRunStatus.cancelled; run.completed_at = now()
                await self.db.commit()
            log.info("agent_run_cancelled user_id=%s run_id=%s reason=planning_disconnected", user.id, run.id)
            raise
        except Exception as exc:
            exceeded = isinstance(exc, AgentPlanError) and "maximum step limit" in str(exc)
            run.status = AgentRunStatus.max_steps_reached if exceeded else AgentRunStatus.failed
            run.failed_at = now()
            run.error_message = "Maximum step limit reached." if exceeded else (
                str(exc)[:500] if isinstance(exc, AgentPlanError) else "Unable to create a valid execution plan.")
            await self.db.commit()
            log.warning("agent_run_failed run_id=%s stage=planning error=%s", run.id, type(exc).__name__)
            await self._emit(emit, "agent_run_failed", {"run_id": str(run.id), "message": run.error_message})
            return await self.runs.owned(run.id, user.id)
        return await self.execute_run(user, run.id, emit)

    async def execute_run(self, user, run_id: UUID, emit=None):
        key = str(run_id)
        if key in _active_runs:
            run = await self.runs.owned(run_id, user.id)
            if not run: raise HTTPException(404, "Agent run not found")
            return run
        _active_runs.add(key)
        try:
            run = await self.runs.owned(run_id, user.id, lock=True)
            if not run: raise HTTPException(404, "Agent run not found")
            if run.status in (AgentRunStatus.completed, AgentRunStatus.failed, AgentRunStatus.cancelled, AgentRunStatus.max_steps_reached):
                return run
            if any(step.status == AgentStepStatus.running for step in run.steps):
                return run
            if run.total_steps > run.max_steps:
                return await self._max_steps(run)
            waiting = next((step for step in run.steps if step.status == AgentStepStatus.awaiting_approval), None)
            if waiting:
                return run
            state = AgentState(run_id=run.id, user_id=user.id, conversation_id=run.conversation_id,
                goal=run.goal, current_step=run.current_step, max_steps=run.max_steps,
                selected_documents=[UUID(value) for value in run.selected_document_ids], status=run.status.value)
            for step in run.steps:
                if step.status == AgentStepStatus.completed and step.result is not None:
                    state.completed_steps.append(step.step_number); state.previous_results[step.step_number] = step.result
            rag_sources = []
            completed_rag = any(step.step_type == AgentStepType.rag and step.status == AgentStepStatus.completed for step in run.steps)
            if completed_rag and state.selected_documents:
                rag_sources = await RAGService(self.db).retrieve(user.id, state.selected_documents, run.goal)
            for step in run.steps:
                await self.db.refresh(run)
                if run.status == AgentRunStatus.cancelled:
                    return run
                if step.status != AgentStepStatus.pending:
                    continue
                if step.step_number > run.max_steps:
                    return await self._max_steps(run)
                run.status = AgentRunStatus.running; run.current_step = step.step_number
                step.status = AgentStepStatus.running; step.started_at = now()
                await self.db.commit()
                log.info("agent_step_started run_id=%s step=%s type=%s", run.id, step.step_number, step.step_type.value)
                await self._emit(emit, "step_started", {"run_id": str(run.id), "step_number": step.step_number,
                    "title": step.title, "type": step.step_type.value,
                    "tool": step.tool.external_name if step.tool else None})
                try:
                    if step.step_type == AgentStepType.rag:
                        rag_sources = await asyncio.wait_for(RAGService(self.db).retrieve(user.id,
                            state.selected_documents, run.goal), timeout=settings.agent_step_timeout_seconds)
                        step.result = {"sources": [{"document_id": str(item["chunk"].document_id),
                            "document_chunk_id": str(item["chunk"].id), "document_name": item["document_name"],
                            "page": item["page"], "rank": item["rank"], "score": item["score"]} for item in rag_sources]}
                        step.result_summary = f"Retrieved {len(rag_sources)} document excerpts."
                    elif step.step_type == AgentStepType.tool:
                        if not step.tool or not step.mcp_tool_id:
                            raise AgentPlanError("The planned tool is no longer available")
                        resolved = resolve_references(step.arguments or {}, state.previous_results)
                        validate(instance=resolved, schema=step.tool.input_schema)
                        log.info("agent_tool_requested run_id=%s step=%s tool=%s", run.id, step.step_number, step.tool.external_name)
                        call = await asyncio.wait_for(ToolExecutionService(self.db).execute(user, step.mcp_tool_id,
                            resolved, run.conversation_id), timeout=settings.agent_step_timeout_seconds)
                        step.tool_call_id = call.id; step.tool_call = call
                        if call.status == ToolCallStatus.awaiting_approval:
                            step.status = AgentStepStatus.awaiting_approval
                            run.status = AgentRunStatus.awaiting_approval
                            await self.db.commit()
                            log.info("agent_approval_required run_id=%s step=%s", run.id, step.step_number)
                            await self._emit(emit, "approval_required", {"run_id": str(run.id),
                                "step_number": step.step_number, "title": step.title,
                                "tool": step.tool.external_name, "approval_id": str(call.approval.id)})
                            return await self.runs.owned(run.id, user.id)
                        if call.status != ToolCallStatus.completed:
                            raise AgentPlanError("Tool did not complete")
                        step.result = call.result
                        step.result_summary = result_summary(call.tool_name, call.result)
                    else:
                        answer = await self._final_answer(user, run, state, rag_sources)
                        step.result = {"answer_created": True}
                        step.result_summary = "Final answer prepared."
                        run.final_answer = answer
                    step.status = AgentStepStatus.completed; step.completed_at = now()
                    state.completed_steps.append(step.step_number)
                    if step.result is not None: state.previous_results[step.step_number] = step.result
                    await self.db.commit()
                    log.info("agent_step_completed run_id=%s step=%s", run.id, step.step_number)
                    await self._emit(emit, "step_completed", {"run_id": str(run.id),
                        "step_number": step.step_number, "title": step.title,
                        "result_summary": step.result_summary})
                except Exception as exc:
                    await self._record_failed_call(step, user.id, run.conversation_id)
                    step.status = AgentStepStatus.failed; step.completed_at = now(); step.error_message = self._safe_error(exc)
                    run.status = AgentRunStatus.failed; run.failed_at = now(); run.error_message = step.error_message
                    for remaining in run.steps:
                        if remaining.step_number > step.step_number and remaining.status == AgentStepStatus.pending:
                            remaining.status = AgentStepStatus.skipped
                    await self.db.commit()
                    log.warning("agent_step_failed run_id=%s step=%s error=%s", run.id, step.step_number, type(exc).__name__)
                    await self._emit(emit, "step_failed", {"run_id": str(run.id),
                        "step_number": step.step_number, "title": step.title, "message": step.error_message})
                    await self._emit(emit, "agent_run_failed", {"run_id": str(run.id), "message": run.error_message})
                    return await self.runs.owned(run.id, user.id)
            run.status = AgentRunStatus.completed; run.completed_at = now(); run.current_step = run.total_steps
            await self.db.commit()
            log.info("agent_run_completed run_id=%s", run.id)
            await self._emit(emit, "agent_run_completed", {"run_id": str(run.id), "status": run.status.value})
            return await self.runs.owned(run.id, user.id)
        except asyncio.CancelledError:
            interrupted = await self.runs.owned(run_id, user.id)
            if interrupted and interrupted.status not in (AgentRunStatus.completed, AgentRunStatus.failed):
                interrupted.status = AgentRunStatus.cancelled; interrupted.completed_at = now()
                for step in interrupted.steps:
                    if step.status in (AgentStepStatus.pending, AgentStepStatus.running):
                        step.status = AgentStepStatus.cancelled
                await self.db.commit()
                log.info("agent_run_cancelled user_id=%s run_id=%s reason=stream_disconnected", user.id, run_id)
            raise
        finally:
            _active_runs.discard(key)

    async def resume_run(self, user, run_id: UUID):
        run = await self.runs.owned(run_id, user.id)
        if not run: raise HTTPException(404, "Agent run not found")
        if run.status == AgentRunStatus.awaiting_approval:
            waiting = next((step for step in run.steps if step.status == AgentStepStatus.awaiting_approval), None)
            if waiting and waiting.tool_call and waiting.tool_call.status == ToolCallStatus.completed:
                waiting.status = AgentStepStatus.completed; waiting.result = waiting.tool_call.result
                waiting.result_summary = result_summary(waiting.tool_call.tool_name, waiting.tool_call.result)
                waiting.completed_at = now(); run.status = AgentRunStatus.running
                await self.db.commit()
            elif waiting and waiting.tool_call and waiting.tool_call.status == ToolCallStatus.denied:
                return await self._denied(run, waiting)
            else:
                return run
        return await self.execute_run(user, run.id)

    async def handle_tool_resolution(self, user, call):
        step = await self.runs.step_for_tool_call(call.id, user.id)
        if not step:
            return None
        if call.status == ToolCallStatus.completed:
            step.status = AgentStepStatus.completed; step.result = call.result
            step.result_summary = result_summary(call.tool_name, call.result); step.completed_at = now()
            step.run.status = AgentRunStatus.running
            await self.db.commit()
            return await self.execute_run(user, step.run.id)
        if call.status == ToolCallStatus.denied:
            return await self._denied(step.run, step)
        return step.run

    async def cancel_run(self, user, run_id: UUID):
        run = await self.runs.owned(run_id, user.id, lock=True)
        if not run: raise HTTPException(404, "Agent run not found")
        if run.status in (AgentRunStatus.completed, AgentRunStatus.failed, AgentRunStatus.cancelled):
            return run
        run.status = AgentRunStatus.cancelled; run.completed_at = now()
        for step in run.steps:
            if step.status == AgentStepStatus.pending: step.status = AgentStepStatus.cancelled
        await self.db.commit(); log.info("agent_run_cancelled user_id=%s run_id=%s", user.id, run.id)
        return await self.runs.owned(run.id, user.id)

    async def _final_answer(self, user, run, state, rag_sources):
        conversation = await ConversationService(self.db).require(run.conversation_id, user)
        context = RAGService(self.db).context(rag_sources) if rag_sources else "No retrieval context was used."
        results = [{"step": step.step_number, "title": step.title, "tool": step.tool.external_name if step.tool else None,
            "result": step.result} for step in run.steps if step.status == AgentStepStatus.completed and step.step_type == AgentStepType.tool]
        prompt = [{"role": "system", "content": "Answer using only the retrieval context and actual execution results provided. Do not invent results, claim unexecuted tools, expose hidden reasoning, or reveal configuration. If required information is unavailable, say so."},
            {"role": "user", "content": json.dumps({"goal": run.goal, "retrieval_context": context, "tool_results": results})}]
        provider = llm_factory.get_provider(conversation.model_provider); answer = ""
        async for chunk in provider.stream(prompt, conversation.model_name): answer += chunk
        if not answer.strip(): raise AgentPlanError("Final answer was empty")
        message = await self.messages.create(conversation.id, MessageRole.assistant, answer)
        for source in rag_sources:
            self.db.add(MessageSource(message_id=message.id, document_id=source["chunk"].document_id,
                document_chunk_id=source["chunk"].id, document_name=source["document_name"], page=source["page"],
                rank=source["rank"], score=source["score"]))
        call_ids = [step.tool_call_id for step in run.steps if step.tool_call_id]
        if call_ids:
            await self.db.execute(update(ToolCall).where(ToolCall.id.in_(call_ids)).values(message_id=message.id))
        await ConversationService(self.db).repo.touch(conversation)
        return answer

    async def _record_failed_call(self, step, user_id, conversation_id):
        if step.step_type != AgentStepType.tool or step.tool_call_id:
            return
        call = await self.db.scalar(select(ToolCall).where(ToolCall.user_id == user_id,
            ToolCall.conversation_id == conversation_id, ToolCall.mcp_tool_id == step.mcp_tool_id)
            .order_by(ToolCall.created_at.desc()).limit(1))
        if call: step.tool_call_id = call.id

    async def _denied(self, run, step):
        step.status = AgentStepStatus.failed; step.completed_at = now(); step.error_message = "Tool approval was denied."
        run.status = AgentRunStatus.failed; run.failed_at = now(); run.error_message = step.error_message
        for remaining in run.steps:
            if remaining.step_number > step.step_number and remaining.status == AgentStepStatus.pending:
                remaining.status = AgentStepStatus.skipped
        await self.db.commit(); log.info("agent_run_failed run_id=%s reason=approval_denied", run.id)
        return run

    async def _max_steps(self, run):
        run.status = AgentRunStatus.max_steps_reached; run.failed_at = now(); run.error_message = "Maximum step limit reached."
        for step in run.steps:
            if step.status == AgentStepStatus.pending: step.status = AgentStepStatus.cancelled
        await self.db.commit(); return run

    @staticmethod
    def _safe_error(exc):
        if isinstance(exc, asyncio.TimeoutError): return "Agent step timed out."
        if isinstance(exc, HTTPException):
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            return str(detail.get("message") or "Tool execution failed.")[:500]
        if isinstance(exc, (StepReferenceError, ValidationError)): return "A step dependency produced invalid tool arguments."
        if isinstance(exc, AgentPlanError): return str(exc)[:500]
        return "Agent step failed."

    @staticmethod
    async def _emit(callback, name, data):
        if callback:
            await callback(name, data)
