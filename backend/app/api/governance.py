from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.dependencies import Db, require_admin
from app.api.mcp import tool_out
from app.models.mcp import ToolPermissionPolicy
from app.models.user import User
from app.repositories.governance_repository import GovernanceRepository
from app.schemas.governance import AuditOut, GovernanceToolUpdate, PolicyCreate, PolicyOut, PolicyUpdate
from app.schemas.mcp import ToolOut
from app.services.governance_service import GovernanceService

router = APIRouter(prefix="/governance", tags=["Governance"])
AdminUser = Annotated[User, Depends(require_admin)]


def policy_out(item):
    return PolicyOut(id=item.id, tool_id=item.tool_id, tool_name=item.tool.external_name,
        user_id=item.user_id, role=item.role, effect=item.effect, approval_mode=item.approval_mode,
        created_at=item.created_at, updated_at=item.updated_at)


@router.get("/tools", response_model=list[ToolOut])
async def tools(_user: AdminUser, db: Db):
    return [tool_out(item) for item in await GovernanceRepository(db).tools()]


@router.patch("/tools/{tool_id}", response_model=ToolOut)
async def update_tool(tool_id: UUID, data: GovernanceToolUpdate, user: AdminUser, db: Db):
    item = await GovernanceRepository(db).tool(tool_id)
    if not item:
        raise HTTPException(404, {"code": "MCP_TOOL_NOT_FOUND", "message": "MCP tool not found."})
    if data.is_enabled is not None: item.is_enabled = data.is_enabled
    if data.risk_level is not None: item.risk_level = data.risk_level
    if data.approval_mode is not None:
        item.approval_mode = data.approval_mode
        item.requires_approval = data.approval_mode == "always"
    await GovernanceService(db).record_event(user.id, "tool_governance_updated", tool_id=item.id,
        metadata=data.model_dump(exclude_none=True))
    await db.commit(); await db.refresh(item)
    return tool_out(item)


@router.get("/policies", response_model=list[PolicyOut])
async def policies(_user: AdminUser, db: Db):
    return [policy_out(item) for item in await GovernanceRepository(db).policies()]


@router.post("/policies", response_model=PolicyOut, status_code=201)
async def create_policy(data: PolicyCreate, user: AdminUser, db: Db):
    repo = GovernanceRepository(db)
    if not await repo.tool(data.tool_id):
        raise HTTPException(404, {"code": "MCP_TOOL_NOT_FOUND", "message": "MCP tool not found."})
    if await repo.conflicting_policy(data.tool_id, data.user_id, data.role):
        raise HTTPException(409, {"code": "GOVERNANCE_POLICY_CONFLICT", "message": "A policy already exists for this tool and subject."})
    item = ToolPermissionPolicy(**data.model_dump())
    db.add(item); await db.flush()
    await GovernanceService(db).record_event(user.id, "tool_policy_created", tool_id=item.tool_id,
        metadata={"policy_id": str(item.id), "effect": item.effect, "role": item.role,
            "subject_user_id": str(item.user_id) if item.user_id else None})
    await db.commit()
    return policy_out(await repo.policy(item.id))


@router.patch("/policies/{policy_id}", response_model=PolicyOut)
async def update_policy(policy_id: UUID, data: PolicyUpdate, user: AdminUser, db: Db):
    repo = GovernanceRepository(db); item = await repo.policy(policy_id)
    if not item:
        raise HTTPException(404, {"code": "GOVERNANCE_POLICY_NOT_FOUND", "message": "Policy not found."})
    if data.effect is not None: item.effect = data.effect
    if data.approval_mode is not None: item.approval_mode = data.approval_mode
    await GovernanceService(db).record_event(user.id, "tool_policy_updated", tool_id=item.tool_id,
        metadata={"policy_id": str(item.id), **data.model_dump(exclude_none=True)})
    await db.commit(); await db.refresh(item)
    return policy_out(item)


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(policy_id: UUID, user: AdminUser, db: Db):
    repo = GovernanceRepository(db); item = await repo.policy(policy_id)
    if not item:
        raise HTTPException(404, {"code": "GOVERNANCE_POLICY_NOT_FOUND", "message": "Policy not found."})
    tool_id = item.tool_id
    await db.delete(item)
    await GovernanceService(db).record_event(user.id, "tool_policy_deleted", tool_id=tool_id,
        metadata={"policy_id": str(policy_id)})
    await db.commit()
    return Response(status_code=204)


@router.get("/audit", response_model=list[AuditOut])
async def audit(_user: AdminUser, db: Db, limit: int = Query(200, ge=1, le=500)):
    return [AuditOut(id=item.id, actor_user_id=item.actor_user_id, event_type=item.event_type,
        tool_id=item.tool_id, agent_run_id=item.agent_run_id,
        approval_request_id=item.approval_request_id, metadata=item.metadata_json,
        created_at=item.created_at) for item in await GovernanceRepository(db).audit(limit)]
