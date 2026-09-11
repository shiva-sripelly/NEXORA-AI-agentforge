"""Persist controlled agent runs and execution steps."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_agents"
down_revision = "0004_mcp"


def upgrade():
    run_status = postgresql.ENUM("planning", "running", "awaiting_approval", "completed", "failed",
        "cancelled", "max_steps_reached", name="agent_run_status", create_type=False)
    step_type = postgresql.ENUM("tool", "rag", "final", name="agent_step_type", create_type=False)
    step_status = postgresql.ENUM("pending", "running", "awaiting_approval", "completed", "failed",
        "skipped", "cancelled", name="agent_step_status", create_type=False)
    run_status.create(op.get_bind(), checkfirst=True)
    step_type.create(op.get_bind(), checkfirst=True)
    step_status.create(op.get_bind(), checkfirst=True)
    op.create_table("agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("triggering_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("goal", sa.Text(), nullable=False), sa.Column("status", run_status, nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("selected_document_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.String(500)), sa.Column("final_answer", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_conversation_id", "agent_runs", ["conversation_id"])
    op.create_table("agent_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False), sa.Column("step_type", step_type, nullable=False),
        sa.Column("title", sa.String(180), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("mcp_tool_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mcp_tools.id", ondelete="SET NULL")),
        sa.Column("tool_call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tool_calls.id", ondelete="SET NULL")),
        sa.Column("arguments", postgresql.JSONB()), sa.Column("status", step_status, nullable=False),
        sa.Column("result", postgresql.JSONB()), sa.Column("result_summary", sa.Text()),
        sa.Column("error_message", sa.String(500)), sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agent_run_id", "step_number"))
    op.create_index("ix_agent_steps_agent_run_id", "agent_steps", ["agent_run_id"])
    op.create_index("ix_agent_steps_tool_call_id", "agent_steps", ["tool_call_id"], unique=True)


def downgrade():
    op.drop_table("agent_steps")
    op.drop_table("agent_runs")
    postgresql.ENUM(name="agent_step_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="agent_step_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="agent_run_status").drop(op.get_bind(), checkfirst=True)
