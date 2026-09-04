"""Create conversations and messages."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="0002_chat";down_revision="0001_auth"
def upgrade():
 role=postgresql.ENUM("user","assistant","system",name="message_role",create_type=False);role.create(op.get_bind(),checkfirst=True)
 op.create_table("conversations",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("title",sa.String(160),nullable=False),sa.Column("model_provider",sa.String(40),nullable=False),sa.Column("model_name",sa.String(120),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
 op.create_index("ix_conversations_user_id","conversations",["user_id"]);op.create_index("ix_conversations_user_updated","conversations",["user_id","updated_at"])
 op.create_table("messages",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("conversation_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("conversations.id",ondelete="CASCADE"),nullable=False),sa.Column("role",role,nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("token_count",sa.Integer(),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
 op.create_index("ix_messages_conversation_id","messages",["conversation_id"]);op.create_index("ix_messages_created_at","messages",["created_at"]);op.create_index("ix_messages_conversation_created","messages",["conversation_id","created_at"])
def downgrade():
 op.drop_table("messages");op.drop_table("conversations");postgresql.ENUM(name="message_role").drop(op.get_bind(),checkfirst=True)
