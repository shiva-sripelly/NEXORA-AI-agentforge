from uuid import UUID

import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.ai.agents.orchestrator import AgentOrchestrator
from app.api.dependencies import CurrentUser, Db
from app.repositories.agent_repository import AgentRepository
from app.schemas.agent import AgentRunCreate, AgentRunOut, AgentStepOut
from app.services.tool_execution_service import arguments_summary
from app.db.session import SessionLocal

router = APIRouter(prefix="/agents", tags=["Agents"])


def step_out(step):
    approval = step.tool_call.approval if step.tool_call else None
    summary = arguments_summary(step.arguments or {})
    references = sorted({value["$from_step"] for value in _references(step.arguments or {})})
    if references: summary["from_steps"] = references
    return AgentStepOut(id=step.id, step_number=step.step_number, step_type=step.step_type.value,
        title=step.title, description=step.description, tool_name=step.tool.external_name if step.tool else None,
        arguments_summary=summary, status=step.status.value, result_summary=step.result_summary,
        error_message=step.error_message, approval_id=approval.id if approval and approval.status.value == "pending" else None,
        started_at=step.started_at, completed_at=step.completed_at)


def run_out(run):
    return AgentRunOut(id=run.id, conversation_id=run.conversation_id,
        triggering_message_id=run.triggering_message_id, goal=run.goal, status=run.status.value,
        current_step=run.current_step, total_steps=run.total_steps, max_steps=run.max_steps,
        started_at=run.started_at, completed_at=run.completed_at, failed_at=run.failed_at,
        error_message=run.error_message, final_answer=run.final_answer, created_at=run.created_at,
        updated_at=run.updated_at, steps=[step_out(step) for step in run.steps])


def _references(value):
    if isinstance(value, dict):
        if "$from_step" in value: yield value
        else:
            for child in value.values(): yield from _references(child)
    elif isinstance(value, list):
        for child in value: yield from _references(child)


@router.post("/runs", response_model=AgentRunOut, status_code=201)
async def create_run(data: AgentRunCreate, user: CurrentUser, db: Db):
    return run_out(await AgentOrchestrator(db).create_run(user, data))


@router.post("/runs/stream")
async def stream_run(data: AgentRunCreate, user: CurrentUser):
    async def body():
        queue = asyncio.Queue()
        async def emit(name, payload): await queue.put((name, payload))
        async def work():
            try:
                async with SessionLocal() as session:
                    run = await AgentOrchestrator(session).create_run(user, data, emit)
                    await queue.put(("complete", {"run": jsonable_encoder(run_out(run))}))
            except Exception:
                await queue.put(("error", {"code": "AGENT_RUN_FAILED", "message": "Unable to execute agent run."}))
            finally:
                await queue.put(None)
        task = asyncio.create_task(work())
        try:
            while True:
                item = await queue.get()
                if item is None: break
                name, payload = item
                yield f"event: {name}\ndata: {json.dumps(payload)}\n\n"
        finally:
            if not task.done(): task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    return StreamingResponse(body(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/runs", response_model=list[AgentRunOut])
async def runs(user: CurrentUser, db: Db, conversation_id: UUID | None = None,
        limit: int = Query(100, ge=1, le=200)):
    return [run_out(item) for item in await AgentRepository(db).list(user.id, conversation_id, limit)]


@router.get("/runs/{run_id}", response_model=AgentRunOut)
async def get_run(run_id: UUID, user: CurrentUser, db: Db):
    item = await AgentRepository(db).owned(run_id, user.id)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "Agent run not found")
    return run_out(item)


@router.get("/runs/{run_id}/steps", response_model=list[AgentStepOut])
async def steps(run_id: UUID, user: CurrentUser, db: Db):
    item = await AgentRepository(db).owned(run_id, user.id)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "Agent run not found")
    return [step_out(step) for step in item.steps]


@router.post("/runs/{run_id}/resume", response_model=AgentRunOut)
async def resume(run_id: UUID, user: CurrentUser, db: Db):
    return run_out(await AgentOrchestrator(db).resume_run(user, run_id))


@router.post("/runs/{run_id}/cancel", response_model=AgentRunOut)
async def cancel(run_id: UUID, user: CurrentUser, db: Db):
    return run_out(await AgentOrchestrator(db).cancel_run(user, run_id))
