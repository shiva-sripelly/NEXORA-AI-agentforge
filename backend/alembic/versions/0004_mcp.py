"""MCP connections, discovered tools, calls, and approvals."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_mcp"
down_revision = "0003_rag"


def upgrade():
    connection_status = postgresql.ENUM("connected", "disconnected", "error", name="mcp_connection_status", create_type=False)
    call_status = postgresql.ENUM("pending", "awaiting_approval", "running", "completed", "failed", "denied", name="tool_call_status", create_type=False)
    approval_status = postgresql.ENUM("pending", "approved", "denied", name="approval_status", create_type=False)
    connection_status.create(op.get_bind(), checkfirst=True)
    call_status.create(op.get_bind(), checkfirst=True)
    approval_status.create(op.get_bind(), checkfirst=True)
    op.create_table("mcp_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("server_type", sa.String(40), nullable=False),
        sa.Column("transport", sa.String(20), nullable=False), sa.Column("command", sa.String(255)),
        sa.Column("args", postgresql.JSONB()), sa.Column("endpoint", sa.String(500)),
        sa.Column("status", connection_status, nullable=False), sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_mcp_connections_user_id", "mcp_connections", ["user_id"])
    op.create_table("mcp_tools",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mcp_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_name", sa.String(120), nullable=False), sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("input_schema", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="low"),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("connection_id", "external_name"))
    op.create_index("ix_mcp_tools_connection_id", "mcp_tools", ["connection_id"])
    op.create_table("tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("mcp_tool_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mcp_tools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(120), nullable=False), sa.Column("arguments", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", call_status, nullable=False), sa.Column("result", postgresql.JSONB()), sa.Column("error_message", sa.String(500)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_tool_calls_user_id", "tool_calls", ["user_id"])
    op.create_index("ix_tool_calls_message_id", "tool_calls", ["message_id"])
    op.create_table("approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tool_calls.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", approval_status, nullable=False), sa.Column("reason", sa.String(500)),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.create_index("ix_approval_requests_user_id", "approval_requests", ["user_id"])


def downgrade():
    op.drop_table("approval_requests")
    op.drop_table("tool_calls")
    op.drop_table("mcp_tools")
    op.drop_table("mcp_connections")
    postgresql.ENUM(name="approval_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="tool_call_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="mcp_connection_status").drop(op.get_bind(), checkfirst=True)
