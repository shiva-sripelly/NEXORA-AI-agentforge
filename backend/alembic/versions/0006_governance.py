"""Advanced tool governance, approval audit data, and security events."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_governance"
down_revision = "0005_agents"


def upgrade():
    op.execute("ALTER TYPE approval_status ADD VALUE IF NOT EXISTS 'cancelled'")
    op.execute("ALTER TYPE approval_status ADD VALUE IF NOT EXISTS 'expired'")

    op.add_column("mcp_tools", sa.Column("approval_mode", sa.String(20), nullable=True))
    op.execute("UPDATE mcp_tools SET approval_mode = CASE WHEN requires_approval THEN 'always' ELSE 'never' END")
    op.alter_column("mcp_tools", "approval_mode", nullable=False, server_default="never")
    op.create_check_constraint("ck_mcp_tools_approval_mode_values", "mcp_tools",
        "approval_mode IN ('never', 'always', 'risk_based')")
    op.create_check_constraint("ck_mcp_tools_risk_level_values", "mcp_tools",
        "risk_level IN ('low', 'medium', 'high', 'critical')")

    op.add_column("approval_requests", sa.Column("agent_run_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True))
    op.add_column("approval_requests", sa.Column("risk_level", sa.String(20), nullable=True))
    op.add_column("approval_requests", sa.Column("tool_name_snapshot", sa.String(120), nullable=True))
    op.add_column("approval_requests", sa.Column("tool_arguments", postgresql.JSONB(), nullable=True))
    op.add_column("approval_requests", sa.Column("resolution_note", sa.String(500), nullable=True))
    op.add_column("approval_requests", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("""UPDATE approval_requests AS a SET
        risk_level = COALESCE(t.risk_level, 'low'),
        tool_name_snapshot = c.tool_name,
        tool_arguments = '{}'::jsonb,
        expires_at = CASE WHEN a.status = 'pending' THEN a.requested_at + interval '30 minutes' ELSE NULL END
        FROM tool_calls AS c JOIN mcp_tools AS t ON t.id = c.mcp_tool_id
        WHERE a.tool_call_id = c.id""")
    op.alter_column("approval_requests", "risk_level", nullable=False, server_default="low")
    op.alter_column("approval_requests", "tool_name_snapshot", nullable=False, server_default="unknown")
    op.alter_column("approval_requests", "tool_arguments", nullable=False, server_default="{}")
    op.create_index("ix_approval_requests_agent_run_id", "approval_requests", ["agent_run_id"])
    op.create_index("ix_approval_requests_expires_at", "approval_requests", ["expires_at"])

    op.create_table("tool_permission_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mcp_tools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("effect", sa.String(10), nullable=False),
        sa.Column("approval_mode", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("effect IN ('allow', 'deny')", name="ck_tool_permission_policies_effect_values"),
        sa.CheckConstraint("approval_mode IS NULL OR approval_mode IN ('never', 'always', 'risk_based')",
            name="ck_tool_permission_policies_approval_mode_values"),
        sa.CheckConstraint("NOT (user_id IS NOT NULL AND role IS NOT NULL)",
            name="ck_tool_permission_policies_single_subject"))
    op.create_index("ix_tool_permission_policies_tool_id", "tool_permission_policies", ["tool_id"])
    op.create_index("uq_tool_policy_user", "tool_permission_policies", ["tool_id", "user_id"], unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"))
    op.create_index("uq_tool_policy_role", "tool_permission_policies", ["tool_id", "role"], unique=True,
        postgresql_where=sa.text("role IS NOT NULL"))
    op.create_index("uq_tool_policy_global", "tool_permission_policies", ["tool_id"], unique=True,
        postgresql_where=sa.text("user_id IS NULL AND role IS NULL"))

    op.create_table("audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mcp_tools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("tool_permission_policies")
    op.drop_index("ix_approval_requests_expires_at", table_name="approval_requests")
    op.drop_index("ix_approval_requests_agent_run_id", table_name="approval_requests")
    for column in ("expires_at", "resolution_note", "tool_arguments", "tool_name_snapshot", "risk_level", "agent_run_id"):
        op.drop_column("approval_requests", column)
    op.drop_constraint("ck_mcp_tools_risk_level_values", "mcp_tools", type_="check")
    op.drop_constraint("ck_mcp_tools_approval_mode_values", "mcp_tools", type_="check")
    op.drop_column("mcp_tools", "approval_mode")
