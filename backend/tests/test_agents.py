import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.agents.orchestrator import AgentOrchestrator
from app.ai.agents.planner import AgentPlanError, AgentPlanner, PlanValidator
from app.ai.agents.references import StepReferenceError, resolve_references, validate_references
from app.ai.rag.service import RAGService
from app.core.config import settings
from app.db.base import Base
from app.mcp.manager import MCPManager
from app.models.agent import AgentRunStatus, AgentStepStatus
from app.models.conversation import Conversation
from app.models.document import Document, DocumentChunk, DocumentStatus, MessageSource
from app.models.mcp import ApprovalStatus, MCPConnection, MCPConnectionStatus, MCPTool, ToolCall, ToolCallStatus
from app.models.user import User
from app.repositories.agent_repository import AgentRepository
from app.schemas.agent import AgentRunCreate, ExecutionPlan
from app.services.tool_execution_service import ToolExecutionService
from app.repositories.conversation_repository import MessageRepository
from app.ai.llm.factory import llm_factory


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def context(db):
    user = User(name="Agent One", email="agent-one@example.com", password_hash="x")
    other = User(name="Agent Two", email="agent-two@example.com", password_hash="x")
    db.add_all([user, other]); await db.flush()
    conversation = Conversation(user_id=user.id, title="Agent test", model_provider="groq", model_name="test-model")
    db.add(conversation); await db.commit()
    return user, other, conversation


def tool(connection, name, schema, approval=False):
    return MCPTool(connection=connection, external_name=name, display_name=name.replace("_", " ").title(),
        description=name, input_schema=schema, is_enabled=True, requires_approval=approval,
        risk_level="medium" if name == "read_text_file" else "low")


async def configured_tools(db, user, read_approval=False):
    analytics = MCPConnection(user_id=user.id, name="Analytics", server_type="analytics", transport="stdio",
        command="audit", args=[], status=MCPConnectionStatus.connected, is_enabled=True)
    files = MCPConnection(user_id=user.id, name="Files", server_type="file", transport="stdio",
        command="audit", args=[], status=MCPConnectionStatus.connected, is_enabled=True)
    stats = tool(analytics, "calculate_statistics", {"type": "object", "required": ["numbers"],
        "properties": {"numbers": {"type": "array", "items": {"type": "number"}, "minItems": 1}}})
    read = tool(files, "read_text_file", {"type": "object", "required": ["path"],
        "properties": {"path": {"type": "string"}}}, read_approval)
    db.add_all([analytics, files]); await db.commit()
    return stats, read


class FixedPlanner:
    def __init__(self, plan): self.plan = ExecutionPlan.model_validate(plan)
    async def create_plan(self, *_): return self.plan


def multi_plan(path="numbers.txt"):
    return {"goal": "Read numbers and calculate statistics", "steps": [
        {"step_number": 1, "type": "tool", "title": "Read file", "description": None,
            "tool_name": "read_text_file", "arguments": {"path": path}},
        {"step_number": 2, "type": "tool", "title": "Calculate statistics", "description": None,
            "tool_name": "calculate_statistics", "arguments": {"numbers": {"$from_step": 1,
                "path": "content", "transform": "number_list"}}},
        {"step_number": 3, "type": "final", "title": "Prepare answer", "description": None,
            "tool_name": None, "arguments": {}},
    ]}


async def fake_final(*_): return "count 5, sum 150, mean 30, min 10, max 50, median 30"


def test_previous_step_reference_resolution():
    value = {"numbers": {"$from_step": 1, "path": "content", "transform": "number_list"}}
    validate_references(value, 2)
    assert resolve_references(value, {1: {"content": "10\n20\n30"}}) == {"numbers": [10.0, 20.0, 30.0]}


def test_future_and_missing_step_references_are_rejected():
    with pytest.raises(StepReferenceError): validate_references({"$from_step": 2}, 2)
    with pytest.raises(StepReferenceError): resolve_references({"$from_step": 1}, {})


@pytest.mark.asyncio
async def test_planner_normalizes_provider_plan_formatting():
    class Provider:
        async def complete_json(self, *_):
            return {"plan": {"steps": [
                {"number": 1, "kind": "function", "name": "Calculate", "tool": {"name": "calculate_statistics"},
                    "input": '{"numbers":[10,20,30,40,50]}', "depends_on": []},
                {"number": 2, "kind": "final", "name": "Summarize", "arguments": {"unused": True}},
            ]}}
    plan = await AgentPlanner().create_plan(Provider(), "test-model", "Calculate statistics", [], [], 8, True)
    assert plan.goal == "Calculate statistics"
    assert plan.steps[0].step_type == "tool"
    assert plan.steps[0].tool_name == "calculate_statistics"
    assert plan.steps[0].arguments == {"numbers": [10, 20, 30, 40, 50]}
    assert plan.steps[1].step_type == "final" and plan.steps[1].arguments == {}


def test_plan_validation_enforces_limits_and_known_tools():
    class Available: input_schema = {"type": "object"}
    valid = ExecutionPlan.model_validate({"goal": "x", "steps": [
        {"step_number": 1, "type": "final", "title": "Answer"}]})
    PlanValidator().validate(valid, {}, False, 1, 1)
    bad = ExecutionPlan.model_validate({"goal": "x", "steps": [
        {"step_number": 1, "type": "tool", "title": "Unknown", "tool_name": "missing"},
        {"step_number": 2, "type": "final", "title": "Answer"}]})
    with pytest.raises(AgentPlanError): PlanValidator().validate(bad, {"known": Available()}, False, 8, 6)
    with pytest.raises(AgentPlanError): PlanValidator().validate(bad, {}, False, 1, 6)


def test_file_statistics_plan_cannot_replace_step_output_with_hardcoded_numbers():
    class Available:
        input_schema = {"type": "object"}

    plan = ExecutionPlan.model_validate({"goal": "Read numbers.txt and calculate statistics", "steps": [
        {"step_number": 1, "type": "tool", "title": "Read", "tool_name": "read_text_file",
            "arguments": {"path": "numbers.txt"}},
        {"step_number": 2, "type": "tool", "title": "Calculate", "tool_name": "calculate_statistics",
            "arguments": {"numbers": [10, 20, 30, 40, 50]}},
        {"step_number": 3, "type": "final", "title": "Summarize"}]})
    tools = {"read_text_file": Available(), "calculate_statistics": Available()}
    with pytest.raises(AgentPlanError, match="actual text-file result"):
        PlanValidator().validate(plan, tools, False, 8, 6, True,
            ["read_text_file", "calculate_statistics"])


@pytest.mark.asyncio
async def test_sequential_execution_uses_actual_previous_result(db, context, monkeypatch):
    user, _, conversation = context
    await configured_tools(db, user)
    calls = []
    async def execute(_, connection, name, arguments):
        calls.append((name, arguments))
        if name == "read_text_file": return {"path": "numbers.txt", "content": "10\n20\n30\n40\n50"}
        return {"count": 5, "sum": 150, "mean": 30, "min": 10, "max": 50, "median": 30}
    monkeypatch.setattr(MCPManager, "execute", execute)
    monkeypatch.setattr(AgentOrchestrator, "_final_answer", fake_final)
    run = await AgentOrchestrator(db, FixedPlanner(multi_plan())).create_run(user,
        AgentRunCreate(conversation_id=conversation.id, goal="Read and calculate"))
    assert run.status == AgentRunStatus.completed
    assert [name for name, _ in calls] == ["read_text_file", "calculate_statistics"]
    assert calls[1][1]["numbers"] == [10.0, 20.0, 30.0, 40.0, 50.0]
    assert run.steps[1].result["mean"] == 30


@pytest.mark.asyncio
async def test_planner_runs_named_file_through_statistics_and_persists_final(db, context, monkeypatch):
    user, _, conversation = context
    await configured_tools(db, user)
    goal = "Read numbers.txt, calculate statistics for the numbers inside it, and summarize the result."
    planner_payloads = []
    calls = []
    execution_order = []

    class Provider:
        configured = True

        async def complete_json(self, messages, _model):
            payload = json.loads(messages[-1]["content"])
            planner_payloads.append(payload)
            if len(planner_payloads) == 1:
                return {"goal": goal, "steps": [
                    {"step_number": 1, "type": "final", "title": "Summary"}]}
            return multi_plan()

        async def stream(self, *_):
            execution_order.append("final")
            yield "count 5, sum 150, mean 30, min 10, max 50, median 30"

    async def execute(_, _connection, name, arguments):
        calls.append((name, arguments))
        execution_order.append(name)
        if name == "read_text_file":
            return {"path": arguments["path"], "content": "10\n20\n30\n40\n50\n"}
        numbers = arguments["numbers"]
        ordered = sorted(numbers)
        return {"count": len(numbers), "sum": sum(numbers), "mean": sum(numbers) / len(numbers),
            "min": min(numbers), "max": max(numbers), "median": ordered[len(ordered) // 2]}

    monkeypatch.setattr(llm_factory, "get_provider", lambda _: Provider())
    monkeypatch.setattr(MCPManager, "execute", execute)

    run = await AgentOrchestrator(db).create_run(user,
        AgentRunCreate(conversation_id=conversation.id, goal=goal))
    messages = await MessageRepository(db).list(conversation.id)

    assert planner_payloads[0]["required_tool_use"] is True
    assert planner_payloads[0]["required_tools"] == ["read_text_file", "calculate_statistics"]
    assert {item["name"] for item in planner_payloads[0]["available_tools"]} >= {
        "read_text_file", "calculate_statistics"}
    assert len(planner_payloads) == 2  # The final-only plan was rejected and replanned.
    assert [step.tool.external_name if step.tool else None for step in run.steps] == [
        "read_text_file", "calculate_statistics", None]
    assert [step.step_type.value for step in run.steps] == ["tool", "tool", "final"]
    assert [step.status for step in run.steps] == [AgentStepStatus.completed] * 3
    assert [name for name, _ in calls] == ["read_text_file", "calculate_statistics"]
    assert execution_order == ["read_text_file", "calculate_statistics", "final"]
    assert calls[1][1] == {"numbers": [10.0, 20.0, 30.0, 40.0, 50.0]}
    assert run.steps[1].arguments == {"numbers": {
        "$from_step": 1, "path": "content", "transform": "number_list"}}
    assert run.steps[1].result == {"count": 5, "sum": 150.0, "mean": 30.0,
        "min": 10.0, "max": 50.0, "median": 30.0}
    assert run.status == AgentRunStatus.completed
    assert run.final_answer == messages[-1].content
    assert run.final_answer == "count 5, sum 150, mean 30, min 10, max 50, median 30"


@pytest.mark.asyncio
async def test_attached_knowledge_document_uses_rag_then_final_and_persists_source(db, context, monkeypatch):
    user, _, conversation = context
    stats, _ = await configured_tools(db, user)
    analyze = tool(stats.connection, "analyze_text", {"type": "object", "required": ["text"],
        "properties": {"text": {"type": "string"}}})
    document = Document(user_id=user.id, original_filename="agentforge-test.txt",
        display_name="agentforge-test.txt", content_type="text/plain", file_size=270,
        storage_path="knowledge/agentforge-test.txt", status=DocumentStatus.ready, chunk_count=1)
    db.add_all([analyze, document]); await db.flush()
    excerpt = ("The internal project codename is Nebula Forge 4729. AgentForge is an AI workspace "
        "that combines knowledge retrieval with controlled MCP tool execution and persistent agent runs.")
    chunk = DocumentChunk(document_id=document.id, chunk_index=0, content=excerpt,
        embedding=[0.0] * 384, metadata_json={"filename": "agentforge-test.txt"})
    db.add(chunk); await db.commit()

    goal = "According to the document, identify the internal project codename and summarize what AgentForge does."
    planner_payloads = []
    final_payloads = []
    tool_calls = []

    class Provider:
        configured = True

        async def complete_json(self, messages, _model):
            planner_payloads.append(json.loads(messages[-1]["content"]))
            # Reproduce the regression: the model mistakes the attached KB item for a workspace file.
            return {"goal": goal, "steps": [
                {"step_number": 1, "type": "tool", "title": "Read Document",
                    "tool_name": "read_text_file", "arguments": {"path": "agentforge-test.txt"}},
                {"step_number": 2, "type": "tool", "title": "Analyze Text",
                    "tool_name": "analyze_text", "arguments": {"text": {
                        "$from_step": 1, "path": "content"}}},
                {"step_number": 3, "type": "final", "title": "Answer"},
            ]}

        async def stream(self, messages, _model):
            payload = json.loads(messages[-1]["content"])
            final_payloads.append(payload)
            assert excerpt in payload["retrieval_context"]
            yield ("The internal project codename is Nebula Forge 4729. AgentForge is an AI workspace "
                "for knowledge retrieval, controlled MCP tool execution, and persistent agent runs.")

    async def retrieve(_service, requested_user_id, document_ids, question):
        assert requested_user_id == user.id
        assert document_ids == [document.id]
        assert question == goal
        return [{"chunk": chunk, "document_name": document.display_name, "page": None,
            "rank": 1, "score": 0.99}]

    async def execute(*args):
        tool_calls.append(args)
        raise AssertionError("Knowledge Base retrieval must not invoke an MCP tool")

    monkeypatch.setattr(llm_factory, "get_provider", lambda _: Provider())
    monkeypatch.setattr(RAGService, "retrieve", retrieve)
    monkeypatch.setattr(MCPManager, "execute", execute)

    run = await AgentOrchestrator(db).create_run(user, AgentRunCreate(
        conversation_id=conversation.id, goal=goal, document_ids=[document.id]))
    run_id, user_id, conversation_id = run.id, user.id, conversation.id
    messages = await MessageRepository(db).list(conversation.id)
    sources = list((await db.scalars(select(MessageSource))).all())

    assert planner_payloads[0]["required_tools"] == []
    assert planner_payloads[0]["selected_documents"] == [{
        "id": str(document.id), "name": "agentforge-test.txt"}]
    assert [step.step_type.value for step in run.steps] == ["rag", "final"]
    assert all(step.status == AgentStepStatus.completed for step in run.steps)
    assert run.steps[0].result["sources"][0]["content"] == excerpt
    assert tool_calls == []
    assert len(final_payloads) == 1 and excerpt in final_payloads[0]["retrieval_context"]
    assert run.status == AgentRunStatus.completed
    assert run.final_answer == messages[-1].content
    assert "Nebula Forge 4729" in run.final_answer
    assert len(sources) == 1 and sources[0].document_name == "agentforge-test.txt"
    assert sources[0].document_id == document.id and sources[0].document_chunk_id == chunk.id

    db.expunge_all()
    persisted = await AgentRepository(db).owned(run_id, user_id)
    refreshed_messages = await MessageRepository(db).list(conversation_id)
    refreshed_sources = list((await db.scalars(select(MessageSource))).all())
    assert persisted.status == AgentRunStatus.completed
    assert persisted.final_answer == refreshed_messages[-1].content
    assert refreshed_sources[0].document_name == "agentforge-test.txt"


@pytest.mark.asyncio
async def test_approval_pauses_and_resume_is_idempotent(db, context, monkeypatch):
    user, _, conversation = context
    await configured_tools(db, user, read_approval=True)
    invoked = 0
    async def execute(*_):
        nonlocal invoked; invoked += 1
        return {"path": "numbers.txt", "content": "10\n20\n30\n40\n50"}
    monkeypatch.setattr(MCPManager, "execute", execute)
    monkeypatch.setattr(AgentOrchestrator, "_final_answer", fake_final)
    plan = {"goal": "Read", "steps": [
        {"step_number": 1, "type": "tool", "title": "Read", "tool_name": "read_text_file", "arguments": {"path": "numbers.txt"}},
        {"step_number": 2, "type": "final", "title": "Answer"}]}
    run = await AgentOrchestrator(db, FixedPlanner(plan)).create_run(user,
        AgentRunCreate(conversation_id=conversation.id, goal="Read"))
    assert run.status == AgentRunStatus.awaiting_approval and invoked == 0
    call = await ToolExecutionService(db).resolve(user, run.steps[0].tool_call.approval.id, True)
    resumed = await AgentOrchestrator(db).handle_tool_resolution(user, call)
    again = await AgentOrchestrator(db).resume_run(user, run.id)
    assert invoked == 1 and resumed.status == AgentRunStatus.completed and again.status == AgentRunStatus.completed
    with pytest.raises(HTTPException) as repeated:
        await ToolExecutionService(db).resolve(user, run.steps[0].tool_call.approval.id, True)
    assert repeated.value.status_code == 409 and invoked == 1


@pytest.mark.asyncio
async def test_cancel_invalidates_agent_approval_and_blocks_stale_resolution(db, context, monkeypatch):
    user, _, conversation = context
    await configured_tools(db, user, read_approval=True)
    tool_executions = 0
    final_answers = 0

    async def execute(*_):
        nonlocal tool_executions
        tool_executions += 1
        return {"path": "numbers.txt", "content": "10\n20\n30\n40\n50"}

    async def final(*_):
        nonlocal final_answers
        final_answers += 1
        return "must not be generated"

    monkeypatch.setattr(MCPManager, "execute", execute)
    monkeypatch.setattr(AgentOrchestrator, "_final_answer", final)
    run = await AgentOrchestrator(db, FixedPlanner(multi_plan())).create_run(user,
        AgentRunCreate(conversation_id=conversation.id,
            goal="Read numbers.txt, calculate statistics, and summarize."))
    approval_id = run.steps[0].tool_call.approval.id
    tool_call_id = run.steps[0].tool_call.id
    initial_call_count = await db.scalar(select(func.count()).select_from(ToolCall))

    assert run.status == AgentRunStatus.awaiting_approval
    assert run.steps[0].status == AgentStepStatus.awaiting_approval
    assert run.steps[0].tool_call.approval.status == ApprovalStatus.pending
    assert tool_executions == 0

    cancelled = await AgentOrchestrator(db).cancel_run(user, run.id)
    cancelled_at = cancelled.completed_at
    repeated_cancel = await AgentOrchestrator(db).cancel_run(user, run.id)

    assert cancelled.status == repeated_cancel.status == AgentRunStatus.cancelled
    assert repeated_cancel.completed_at == cancelled_at
    assert [step.status for step in repeated_cancel.steps] == [AgentStepStatus.cancelled] * 3
    assert repeated_cancel.steps[0].tool_call.status == ToolCallStatus.denied
    assert repeated_cancel.steps[0].tool_call.approval.status == ApprovalStatus.denied
    assert repeated_cancel.steps[0].tool_call.approval.reason == "Agent run cancelled."

    for approve in (True, False):
        with pytest.raises(HTTPException) as stale:
            await ToolExecutionService(db).resolve(user, approval_id, approve)
        assert stale.value.status_code == 409

    resumed = await AgentOrchestrator(db).resume_run(user, run.id)
    stale_call = SimpleNamespace(id=tool_call_id, status=ToolCallStatus.completed,
        result={"content": "unexpected"}, tool_name="read_text_file")
    handled = await AgentOrchestrator(db).handle_tool_resolution(user, stale_call)
    final = await AgentRepository(db).owned(run.id, user.id)
    final_call_count = await db.scalar(select(func.count()).select_from(ToolCall))

    assert resumed.status == handled.status == final.status == AgentRunStatus.cancelled
    assert [step.status for step in final.steps] == [AgentStepStatus.cancelled] * 3
    assert tool_executions == 0
    assert final_call_count == initial_call_count == 1
    assert final.final_answer is None and final_answers == 0


@pytest.mark.asyncio
async def test_denial_and_cancellation_stop_remaining_steps(db, context, monkeypatch):
    user, _, conversation = context
    await configured_tools(db, user, read_approval=True)
    monkeypatch.setattr(AgentOrchestrator, "_final_answer", fake_final)
    plan = {"goal": "Read", "steps": [
        {"step_number": 1, "type": "tool", "title": "Read", "tool_name": "read_text_file", "arguments": {"path": "numbers.txt"}},
        {"step_number": 2, "type": "final", "title": "Answer"}]}
    run = await AgentOrchestrator(db, FixedPlanner(plan)).create_run(user,
        AgentRunCreate(conversation_id=conversation.id, goal="Read"))
    cancelled = await AgentOrchestrator(db).cancel_run(user, run.id)
    assert cancelled.status == AgentRunStatus.cancelled
    assert cancelled.steps[1].status == AgentStepStatus.cancelled

    second = await AgentOrchestrator(db, FixedPlanner(plan)).create_run(user,
        AgentRunCreate(conversation_id=conversation.id, goal="Read again"))
    denied_call = await ToolExecutionService(db).resolve(user, second.steps[0].tool_call.approval.id, False)
    denied = await AgentOrchestrator(db).handle_tool_resolution(user, denied_call)
    assert denied.status == AgentRunStatus.failed and denied.steps[1].status == AgentStepStatus.skipped
    assert denied.steps[0].result is None


@pytest.mark.asyncio
async def test_agent_run_ownership_isolation(db, context, monkeypatch):
    user, other, conversation = context
    monkeypatch.setattr(AgentOrchestrator, "_final_answer", fake_final)
    plan = {"goal": "Answer", "steps": [{"step_number": 1, "type": "final", "title": "Answer"}]}
    run = await AgentOrchestrator(db, FixedPlanner(plan)).create_run(user,
        AgentRunCreate(conversation_id=conversation.id, goal="Answer"))
    assert await AgentRepository(db).owned(run.id, other.id) is None
    assert await AgentRepository(db).list(other.id) == []
    with pytest.raises(HTTPException): await AgentOrchestrator(db).cancel_run(other, run.id)


@pytest.mark.asyncio
async def test_final_answer_is_persisted_in_conversation(db, context, monkeypatch):
    user, _, conversation = context
    class Provider:
        async def stream(self, *_):
            yield "Grounded final answer."
    monkeypatch.setattr(llm_factory, "get_provider", lambda _: Provider())
    plan = {"goal": "Answer", "steps": [{"step_number": 1, "type": "final", "title": "Answer"}]}
    run = await AgentOrchestrator(db, FixedPlanner(plan)).create_run(user,
        AgentRunCreate(conversation_id=conversation.id, goal="Answer"))
    messages = await MessageRepository(db).list(conversation.id)
    assert run.status == AgentRunStatus.completed and run.final_answer == "Grounded final answer."
    assert [message.content for message in messages] == ["Answer", "Grounded final answer."]


@pytest.mark.asyncio
async def test_tool_run_links_final_message_without_lazy_relationship_load(db, context, monkeypatch):
    user, _, conversation = context
    await configured_tools(db, user)
    class Provider:
        async def stream(self, *_):
            yield "count 5, sum 150, mean 30, min 10, max 50, median 30"
    async def execute(*_):
        return {"count": 5, "sum": 150, "mean": 30, "min": 10, "max": 50, "median": 30}
    monkeypatch.setattr(llm_factory, "get_provider", lambda _: Provider())
    monkeypatch.setattr(MCPManager, "execute", execute)
    plan = {"goal": "Calculate statistics", "steps": [
        {"step_number": 1, "type": "tool", "title": "Calculate statistics",
            "tool_name": "calculate_statistics", "arguments": {"numbers": [10, 20, 30, 40, 50]}},
        {"step_number": 2, "type": "final", "title": "Summarize"}]}
    run = await AgentOrchestrator(db, FixedPlanner(plan)).create_run(user,
        AgentRunCreate(conversation_id=conversation.id, goal="Use the statistics tool"))
    messages = await MessageRepository(db).list(conversation.id)
    assert run.status == AgentRunStatus.completed and run.total_steps == 2
    assert run.steps[0].tool_call_id is not None
    assert run.steps[0].tool_call.message_id == messages[-1].id


@pytest.mark.asyncio
async def test_failed_tool_does_not_create_result(db, context, monkeypatch):
    user, _, conversation = context
    await configured_tools(db, user)
    async def fail(*_): raise HTTPException(502, {"message": "Tool execution failed."})
    monkeypatch.setattr(ToolExecutionService, "execute", fail)
    plan = {"goal": "Calculate", "steps": [
        {"step_number": 1, "type": "tool", "title": "Calculate", "tool_name": "calculate_statistics", "arguments": {"numbers": [1, 2]}},
        {"step_number": 2, "type": "final", "title": "Answer"}]}
    run = await AgentOrchestrator(db, FixedPlanner(plan)).create_run(user,
        AgentRunCreate(conversation_id=conversation.id, goal="Calculate"))
    assert run.status == AgentRunStatus.failed
    assert run.steps[0].result is None and run.final_answer is None


@pytest.mark.asyncio
async def test_real_file_to_analytics_mcp_flow(db, context, monkeypatch, tmp_path):
    user, _, conversation = context
    await configured_tools(db, user)
    Path(tmp_path, "numbers.txt").write_text("10\n20\n30\n40\n50\n", encoding="utf-8")
    monkeypatch.setattr(settings, "mcp_file_root", str(tmp_path))
    monkeypatch.setattr(AgentOrchestrator, "_final_answer", fake_final)
    run = await AgentOrchestrator(db, FixedPlanner(multi_plan())).create_run(user,
        AgentRunCreate(conversation_id=conversation.id, goal="Read numbers.txt and calculate statistics"))
    assert run.status == AgentRunStatus.completed
    assert run.steps[0].tool_call.status == ToolCallStatus.completed
    assert run.steps[1].tool_call.status == ToolCallStatus.completed
    assert run.steps[1].result == {"count": 5, "sum": 150, "mean": 30, "min": 10, "max": 50, "median": 30}
