from pathlib import Path
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.mcp.client import MCPClient
from app.mcp.permissions import require_executable
from app.mcp.transport import local_server_config
from app.models.mcp import ApprovalStatus, MCPConnection, MCPConnectionStatus, MCPTool, ToolCallStatus
from app.models.user import User
from app.repositories.mcp_repository import MCPRepository
from app.services.mcp_service import MCPService
from app.services.tool_execution_service import ToolExecutionService
from app.schemas.mcp import ConnectionCreate
from pydantic import ValidationError


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
async def users(db):
    one = User(name="MCP One", email="mcp-one@example.com", password_hash="x")
    two = User(name="MCP Two", email="mcp-two@example.com", password_hash="x")
    db.add_all([one, two]); await db.commit()
    return one, two


async def configured_tool(db, user, *, enabled=True, connection_enabled=True, approval=False):
    connection = MCPConnection(user_id=user.id, name="Analytics", server_type="analytics", transport="stdio",
        command="stored-for-audit", args=[], status=MCPConnectionStatus.connected, is_enabled=connection_enabled)
    tool = MCPTool(connection=connection, external_name="calculate_statistics", display_name="Calculate Statistics",
        description="Statistics", input_schema={"type": "object", "required": ["numbers"],
        "properties": {"numbers": {"type": "array", "items": {"type": "number"}, "minItems": 1}}},
        is_enabled=enabled, requires_approval=approval, risk_level="low")
    db.add(connection); await db.commit()
    return connection, tool


@pytest.mark.asyncio
async def test_connection_and_tool_ownership(db, users):
    one, two = users
    connection, tool = await configured_tool(db, one)
    assert await MCPService(db).require_connection(connection.id, one.id)
    with pytest.raises(HTTPException) as denied:
        await MCPService(db).require_connection(connection.id, two.id)
    assert denied.value.status_code == 404
    assert await MCPRepository(db).tool(tool.id, two.id) is None


def test_connection_registration_rejects_arbitrary_commands():
    with pytest.raises(ValidationError):
        ConnectionCreate.model_validate({"server_type": "analytics", "command": "powershell"})


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_enabled,connection_enabled", [(False, True), (True, False)])
async def test_disabled_resources_cannot_execute(db, users, tool_enabled, connection_enabled):
    one, _ = users
    _, tool = await configured_tool(db, one, enabled=tool_enabled, connection_enabled=connection_enabled)
    with pytest.raises(HTTPException) as denied:
        require_executable(tool)
    assert denied.value.status_code == 409


@pytest.mark.asyncio
async def test_invalid_arguments_rejected_before_execution(db, users):
    one, _ = users
    _, tool = await configured_tool(db, one)
    with pytest.raises(HTTPException) as invalid:
        await ToolExecutionService(db).execute(one, tool.id, {"numbers": []})
    assert invalid.value.detail["code"] == "MCP_INVALID_ARGUMENTS"


@pytest.mark.asyncio
async def test_approval_is_persisted_and_denial_does_not_execute(db, users):
    one, _ = users
    _, tool = await configured_tool(db, one, approval=True)
    service = ToolExecutionService(db)
    call = await service.execute(one, tool.id, {"numbers": [1, 2, 3]})
    assert call.status == ToolCallStatus.awaiting_approval
    assert call.approval.status == ApprovalStatus.pending
    denied = await service.resolve(one, call.approval.id, False)
    assert denied.status == ToolCallStatus.denied and denied.result is None


@pytest.mark.asyncio
async def test_approved_call_executes_only_after_approval(db, users, monkeypatch):
    one, _ = users
    _, tool = await configured_tool(db, one, approval=True)
    invoked = 0
    async def fake_execute(*_):
        nonlocal invoked
        invoked += 1
        return {"count": 1, "sum": 9, "mean": 9, "min": 9, "max": 9, "median": 9}
    service = ToolExecutionService(db)
    monkeypatch.setattr(service.manager, "execute", fake_execute)
    call = await service.execute(one, tool.id, {"numbers": [9]})
    assert invoked == 0
    resolved = await service.resolve(one, call.approval.id, True)
    assert invoked == 1 and resolved.status == ToolCallStatus.completed


@pytest.mark.asyncio
async def test_real_analytics_mcp_discovery_and_execution():
    command, args, env = local_server_config("analytics")
    async with MCPClient(command, args, env) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} >= {"calculate_statistics", "analyze_text"}
        result = await client.call_tool("calculate_statistics", {"numbers": [10, 20, 30, 40, 50]})
    assert result.is_error is False
    assert result.data == {"count": 5, "sum": 150, "mean": 30, "min": 10, "max": 50, "median": 30}


def test_file_server_blocks_traversal(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_FILE_ROOT", str(tmp_path))
    import importlib
    server = importlib.import_module("mcp_servers.file_server.server")
    monkeypatch.setattr(server, "ROOT", tmp_path.resolve())
    with pytest.raises(ValueError, match="outside"):
        server.safe_path("../../.env")
    with pytest.raises(ValueError, match="outside"):
        server.safe_path(str(Path(tmp_path.anchor) / "Windows"))


@pytest.mark.asyncio
async def test_tool_call_persistence(db, users, monkeypatch):
    one, _ = users
    _, tool = await configured_tool(db, one)
    async def fake_execute(*_): return {"count": 3, "sum": 6, "mean": 2, "min": 1, "max": 3, "median": 2}
    service = ToolExecutionService(db)
    monkeypatch.setattr(service.manager, "execute", fake_execute)
    call = await service.execute(one, tool.id, {"numbers": [1, 2, 3]})
    assert call.status == ToolCallStatus.completed
    stored = await service.calls.owned(call.id, one.id)
    assert stored and stored.result["median"] == 2
