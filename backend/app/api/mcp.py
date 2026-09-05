import logging
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import CurrentUser, Db
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.mcp_repository import MCPRepository
from app.repositories.tool_call_repository import ToolCallRepository
from app.schemas.mcp import ApprovalOut, ConnectionCreate, ConnectionOut, ToolCallOut, ToolExecute, ToolOut, ToolUpdate
from app.services.mcp_service import MCPService
from app.services.tool_execution_service import ToolExecutionService, arguments_summary, result_summary

router = APIRouter(prefix="/mcp", tags=["MCP"])
log = logging.getLogger(__name__)


def connection_out(item):
    return ConnectionOut(id=item.id, name=item.name, server_type=item.server_type, transport=item.transport,
        status=item.status.value, is_enabled=item.is_enabled, created_at=item.created_at, updated_at=item.updated_at)


def tool_out(item):
    return ToolOut(id=item.id, connection_id=item.connection_id, connection_name=item.connection.name,
        external_name=item.external_name, display_name=item.display_name, description=item.description,
        input_schema=item.input_schema, is_enabled=item.is_enabled, requires_approval=item.requires_approval,
        risk_level=item.risk_level, discovered_at=item.discovered_at, updated_at=item.updated_at)


def call_out(item, final_message_content=None):
    return ToolCallOut(id=item.id, conversation_id=item.conversation_id, message_id=item.message_id,
        mcp_tool_id=item.mcp_tool_id, tool_name=item.tool_name, status=item.status.value,
        arguments_summary=arguments_summary(item.arguments), result_summary=result_summary(item.tool_name, item.result),
        error_message=item.error_message, started_at=item.started_at, completed_at=item.completed_at,
        created_at=item.created_at, approval_id=item.approval.id if item.approval else None,
        final_message_content=final_message_content)


def approval_out(item):
    return ApprovalOut(id=item.id, tool_call_id=item.tool_call_id, tool_name=item.tool_call.tool_name,
        status=item.status.value, risk_level=item.tool_call.tool.risk_level,
        arguments_summary=arguments_summary(item.tool_call.arguments), requested_at=item.requested_at,
        resolved_at=item.resolved_at)


@router.get("/connections", response_model=list[ConnectionOut])
async def connections(user: CurrentUser, db: Db):
    return [connection_out(item) for item in await MCPRepository(db).connections(user.id)]


@router.post("/connections", response_model=ConnectionOut, status_code=201)
async def create_connection(data: ConnectionCreate, user: CurrentUser, db: Db):
    return connection_out(await MCPService(db).create(user, data.server_type, data.name))


@router.get("/connections/{connection_id}", response_model=ConnectionOut)
async def get_connection(connection_id: UUID, user: CurrentUser, db: Db):
    return connection_out(await MCPService(db).require_connection(connection_id, user.id))


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(connection_id: UUID, user: CurrentUser, db: Db):
    item = await MCPService(db).require_connection(connection_id, user.id)
    await db.delete(item); await db.commit()
    log.info("mcp_connection_deleted user_id=%s connection_id=%s", user.id, item.id)
    return Response(status_code=204)


@router.post("/connections/{connection_id}/connect", response_model=list[ToolOut])
@router.post("/connections/{connection_id}/refresh-tools", response_model=list[ToolOut])
async def connect(connection_id: UUID, user: CurrentUser, db: Db):
    service = MCPService(db)
    item = await service.require_connection(connection_id, user.id)
    return [tool_out(tool) for tool in await service.refresh(item) if tool.connection_id == item.id]


@router.get("/tools", response_model=list[ToolOut])
async def tools(user: CurrentUser, db: Db):
    return [tool_out(item) for item in await MCPRepository(db).tools(user.id)]


@router.patch("/tools/{tool_id}", response_model=ToolOut)
async def update_tool(tool_id: UUID, data: ToolUpdate, user: CurrentUser, db: Db):
    item = await MCPRepository(db).tool(tool_id, user.id)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, {"code": "MCP_TOOL_NOT_FOUND", "message": "MCP tool not found."})
    if data.is_enabled is not None: item.is_enabled = data.is_enabled
    if data.requires_approval is not None: item.requires_approval = data.requires_approval
    await db.commit(); await db.refresh(item)
    return tool_out(item)


@router.post("/tools/{tool_id}/execute", response_model=ToolCallOut)
async def execute_tool(tool_id: UUID, data: ToolExecute, user: CurrentUser, db: Db):
    return call_out(await ToolExecutionService(db).execute(user, tool_id, data.arguments))


@router.get("/tool-calls", response_model=list[ToolCallOut])
async def tool_calls(user: CurrentUser, db: Db, limit: int = Query(100, ge=1, le=200)):
    return [call_out(item) for item in await ToolCallRepository(db).list(user.id, limit)]


@router.get("/tool-calls/{call_id}", response_model=ToolCallOut)
async def tool_call(call_id: UUID, user: CurrentUser, db: Db):
    from fastapi import HTTPException
    item = await ToolCallRepository(db).owned(call_id, user.id)
    if not item: raise HTTPException(404, {"code": "MCP_TOOL_CALL_NOT_FOUND", "message": "Tool call not found."})
    return call_out(item)


@router.get("/approvals", response_model=list[ApprovalOut])
async def approvals(user: CurrentUser, db: Db, pending: bool = True):
    return [approval_out(item) for item in await ApprovalRepository(db).list(user.id, pending)]


@router.post("/approvals/{approval_id}/approve", response_model=ToolCallOut)
async def approve(approval_id: UUID, user: CurrentUser, db: Db):
    service = ToolExecutionService(db)
    call = await service.resolve(user, approval_id, True)
    return call_out(call, await service.continue_approved_chat(user, call))


@router.post("/approvals/{approval_id}/deny", response_model=ToolCallOut)
async def deny(approval_id: UUID, user: CurrentUser, db: Db):
    return call_out(await ToolExecutionService(db).resolve(user, approval_id, False))
