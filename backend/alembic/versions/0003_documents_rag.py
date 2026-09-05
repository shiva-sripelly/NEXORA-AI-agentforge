"""Documents, pgvector chunks, and persistent message sources."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector
revision="0003_rag";down_revision="0002_chat"
def upgrade():
 op.execute("CREATE EXTENSION IF NOT EXISTS vector")
 status=postgresql.ENUM("uploaded","processing","ready","failed",name="document_status",create_type=False);status.create(op.get_bind(),checkfirst=True)
 op.create_table("documents",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("original_filename",sa.String(255),nullable=False),sa.Column("display_name",sa.String(255),nullable=False),sa.Column("content_type",sa.String(100),nullable=False),sa.Column("file_size",sa.BigInteger(),nullable=False),sa.Column("storage_path",sa.String(500),nullable=False),sa.Column("status",status,nullable=False),sa.Column("processing_error",sa.String(500)),sa.Column("chunk_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
 op.create_index("ix_documents_user_id","documents",["user_id"]);op.create_index("ix_documents_status","documents",["status"]);op.create_index("ix_documents_user_created","documents",["user_id","created_at"])
 op.create_table("document_chunks",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("document_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("documents.id",ondelete="CASCADE"),nullable=False),sa.Column("chunk_index",sa.Integer(),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("embedding",Vector(384),nullable=False),sa.Column("token_count",sa.Integer()),sa.Column("metadata_json",postgresql.JSONB(),nullable=False,server_default="{}"),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("document_id","chunk_index"))
 op.create_index("ix_document_chunks_document_id","document_chunks",["document_id"]);op.execute("CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops)")
 op.create_table("message_sources",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("message_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("messages.id",ondelete="CASCADE"),nullable=False),sa.Column("document_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("documents.id",ondelete="SET NULL")),sa.Column("document_chunk_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("document_chunks.id",ondelete="SET NULL")),sa.Column("document_name",sa.String(255),nullable=False),sa.Column("page",sa.Integer()),sa.Column("rank",sa.Integer(),nullable=False),sa.Column("score",sa.Float(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
 op.create_index("ix_message_sources_message_id","message_sources",["message_id"])
def downgrade():
 op.drop_table("message_sources");op.drop_table("document_chunks");op.drop_table("documents");postgresql.ENUM(name="document_status").drop(op.get_bind(),checkfirst=True)
