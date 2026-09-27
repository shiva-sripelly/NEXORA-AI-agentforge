from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import require_admin
from app.core.config import settings
from app.db.base import Base
from app.models.mcp import (ApprovalStatus, AuditLog, MCPConnection, MCPConnectionStatus, MCPTool,
    ToolCallStatus, ToolPermissionPolicy)
from app.models.user import User, UserRole
from app.repositories.approval_repository import ApprovalRepository
from app.services.governance_service import GovernanceService
from app.services.tool_execution_service import ToolExecutionService


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
async def governed(db):
    user = User(name="Governed User", email="governed@example.com", password_hash="x", role=UserRole.USER)
    other = User(name="Other User", email="other-governed@example.com", password_hash="x")
    admin = User(name="Admin", email="governance-admin@example.com", password_hash="x", role=UserRole.ADMIN)
    db.add_all([user, other, admin]); await db.flush()
    connection = MCPConnection(user_id=user.id, name="Files", server_type="file", transport="stdio",
        command="audit-only", args=[], status=MCPConnectionStatus.connected, is_enabled=True)
    tool = MCPTool(connection=connection, external_name="read_text_file", display_name="Read Text File",
        description="Read a workspace file", input_schema={"type": "object", "required": ["path"],
            "properties": {"path": {"type": "string"}}}, is_enabled=True, requires_approval=False,
        approval_mode="never", risk_level="medium")
    db.add(connection); await db.commit()
    return user, other, admin, tool


@pytest.mark.asyncio
async def test_low_risk_never_policy_allows(db, governed):
    user, _, _, tool = governed
    tool.risk_level = "low"; tool.approval_mode = "never"
    decision = await GovernanceService(db).evaluate_tool_execution(user, tool, {"path": "safe.txt"})
    assert decision.decision == "allow" and decision.requires_approval is False


@pytest.mark.asyncio
async def test_medium_risk_always_policy_requires_approval(db, governed):
    user, _, _, tool = governed
    tool.approval_mode = "always"
    decision = await GovernanceService(db).evaluate_tool_execution(user, tool, {"path": "project.txt"})
    assert decision.decision == "require_approval"
    assert decision.risk_level == "medium" and decision.requires_approval is True


@pytest.mark.asyncio
async def test_risk_based_threshold_is_explicit(db, governed, monkeypatch):
    user, _, _, tool = governed
    tool.approval_mode = "risk_based"
    monkeypatch.setattr(settings, "tool_approval_risk_threshold", "medium")
    decision = await GovernanceService(db).evaluate_tool_execution(user, tool, {"path": "project.txt"})
    assert decision.decision == "require_approval"


@pytest.mark.asyncio
async def test_explicit_deny_and_disabled_tool_are_denied(db, governed):
    user, _, _, tool = governed
    db.add(ToolPermissionPolicy(tool_id=tool.id, user_id=user.id, effect="deny"))
    await db.commit()
    decision = await GovernanceService(db).evaluate_tool_execution(user, tool, {"path": "project.txt"})
    assert decision.decision == "deny" and "policy" in decision.reason.casefold()
    tool.is_enabled = False; await db.commit()
    disabled = await GovernanceService(db).evaluate_tool_execution(user, tool, {"path": "project.txt"})
    assert disabled.decision == "deny" and "disabled" in disabled.reason.casefold()


@pytest.mark.asyncio
@pytest.mark.parametrize("user_effect,role_effect,expected", [
    ("allow", "deny", "allow"), ("deny", "allow", "deny")])
async def test_user_policy_precedes_role_policy(db, governed, user_effect, role_effect, expected):
    user, _, _, tool = governed
    db.add_all([
        ToolPermissionPolicy(tool_id=tool.id, role="USER", effect=role_effect, approval_mode="never"),
        ToolPermissionPolicy(tool_id=tool.id, user_id=user.id, effect=user_effect, approval_mode="never"),
    ])
    await db.commit()
    decision = await GovernanceService(db).evaluate_tool_execution(user, tool, {"path": "project.txt"})
    assert decision.decision == expected
    assert decision.matched_policy.startswith("policy:")


@pytest.mark.asyncio
async def test_direct_protected_call_waits_and_persists_safe_snapshot(db, governed):
    user, _, _, tool = governed
    tool.approval_mode = "always"; await db.commit()
    service = ToolExecutionService(db)
    call = await service.execute(user, tool.id, {"path": "project-info.txt", "token": "must-not-persist"})
    assert call.status == ToolCallStatus.awaiting_approval
    assert call.approval.reason and call.approval.risk_level == "medium"
    assert call.approval.tool_arguments == {"path": "project-info.txt", "token": "[REDACTED]"}


@pytest.mark.asyncio
async def test_direct_denied_call_never_executes(db, governed, monkeypatch):
    user, _, _, tool = governed
    db.add(ToolPermissionPolicy(tool_id=tool.id, user_id=user.id, effect="deny")); await db.commit()
    invoked = 0
    async def execute(*_):
        nonlocal invoked; invoked += 1
    service = ToolExecutionService(db); monkeypatch.setattr(service.manager, "execute", execute)
    with pytest.raises(HTTPException) as denied:
        await service.execute(user, tool.id, {"path": "project.txt"})
    assert denied.value.status_code == 403 and invoked == 0


@pytest.mark.asyncio
async def test_direct_low_risk_call_executes_without_approval(db, governed, monkeypatch):
    user, _, _, tool = governed
    tool.risk_level = "low"; tool.approval_mode = "never"; await db.commit()
    service = ToolExecutionService(db)
    monkeypatch.setattr(service.manager, "execute", lambda *_: _async_result({"content": "safe"}))
    call = await service.execute(user, tool.id, {"path": "project.txt"})
    assert call.status == ToolCallStatus.completed and call.approval is None


async def _async_result(value):
    return value


@pytest.mark.asyncio
async def test_expired_approval_rejects_execution_and_fails_call(db, governed, monkeypatch):
    user, _, _, tool = governed
    tool.approval_mode = "always"; await db.commit()
    service = ToolExecutionService(db); invoked = 0
    async def execute(*_):
        nonlocal invoked; invoked += 1
    monkeypatch.setattr(service.manager, "execute", execute)
    call = await service.execute(user, tool.id, {"path": "project.txt"})
    call.approval.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1); await db.commit()
    with pytest.raises(HTTPException) as expired:
        await service.resolve(user, call.approval.id, True)
    assert expired.value.detail["code"] == "MCP_APPROVAL_EXPIRED"
    assert call.approval.status == ApprovalStatus.expired
    assert call.status == ToolCallStatus.failed and invoked == 0


@pytest.mark.asyncio
async def test_double_approve_and_deny_after_approve_execute_once(db, governed, monkeypatch):
    user, _, _, tool = governed
    tool.approval_mode = "always"; await db.commit()
    service = ToolExecutionService(db); invoked = 0
    async def execute(*_):
        nonlocal invoked; invoked += 1
        return {"content": "approved"}
    monkeypatch.setattr(service.manager, "execute", execute)
    call = await service.execute(user, tool.id, {"path": "project.txt"})
    await service.resolve(user, call.approval.id, True, "Reviewed")
    for approve in (True, False):
        with pytest.raises(HTTPException) as repeated:
            await service.resolve(user, call.approval.id, approve)
        assert repeated.value.status_code == 409
    assert invoked == 1 and call.approval.status == ApprovalStatus.approved


@pytest.mark.asyncio
async def test_approval_ownership_and_admin_guard(db, governed):
    user, other, admin, tool = governed
    tool.approval_mode = "always"; await db.commit()
    service = ToolExecutionService(db)
    call = await service.execute(user, tool.id, {"path": "project.txt"})
    assert await ApprovalRepository(db).owned(call.approval.id, other.id) is None
    with pytest.raises(HTTPException) as hidden:
        await service.resolve(other, call.approval.id, True)
    assert hidden.value.status_code == 404
    with pytest.raises(HTTPException) as forbidden:
        await require_admin(user)
    assert forbidden.value.status_code == 403
    assert await require_admin(admin) is admin


@pytest.mark.asyncio
async def test_audit_metadata_redacts_secrets(db, governed):
    user, _, _, tool = governed
    await GovernanceService(db).evaluate_tool_execution(user, tool,
        {"path": "project.txt", "api_key": "private", "text": "potentially sensitive body"})
    await db.commit()
    event = await db.scalar(select(AuditLog).where(AuditLog.event_type == "tool_policy_evaluated"))
    assert event.metadata_json["arguments"]["api_key"] == "[REDACTED]"
    assert event.metadata_json["arguments"]["text"] == "[TEXT 20 characters]"
