"""Create users and user sessions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_auth"
down_revision = None


def upgrade():
    role = postgresql.ENUM("USER", "ADMIN", name="user_role", create_type=False)
    role.create(op.get_bind(), checkfirst=True)
    op.create_table("users", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("email", sa.String(320), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", role, nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("email", name="uq_users_email"))
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table("user_sessions", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"))
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"]); op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"])


def downgrade():
    op.drop_table("user_sessions"); op.drop_table("users"); postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
