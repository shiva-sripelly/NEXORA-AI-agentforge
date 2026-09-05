import enum
from datetime import datetime
from uuid import UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger,DateTime,Enum,ForeignKey,Integer,JSON,String,Text,func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.db.base import Base,TimestampMixin,UUIDMixin

class DocumentStatus(str,enum.Enum):uploaded="uploaded";processing="processing";ready="ready";failed="failed"
class Document(UUIDMixin,TimestampMixin,Base):
 __tablename__="documents"
 user_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("users.id",ondelete="CASCADE"),index=True)
 original_filename:Mapped[str]=mapped_column(String(255));display_name:Mapped[str]=mapped_column(String(255));content_type:Mapped[str]=mapped_column(String(100));file_size:Mapped[int]=mapped_column(BigInteger);storage_path:Mapped[str]=mapped_column(String(500));status:Mapped[DocumentStatus]=mapped_column(Enum(DocumentStatus,name="document_status"),index=True);processing_error:Mapped[str|None]=mapped_column(String(500),nullable=True);chunk_count:Mapped[int]=mapped_column(Integer,default=0)
 chunks=relationship("DocumentChunk",back_populates="document",cascade="all, delete-orphan")
class DocumentChunk(UUIDMixin,Base):
 __tablename__="document_chunks"
 document_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("documents.id",ondelete="CASCADE"),index=True);chunk_index:Mapped[int]=mapped_column(Integer);content:Mapped[str]=mapped_column(Text);embedding:Mapped[list[float]]=mapped_column(Vector(384));token_count:Mapped[int|None]=mapped_column(Integer,nullable=True);metadata_json:Mapped[dict]=mapped_column(JSON,default=dict);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now());document=relationship("Document",back_populates="chunks")
class MessageSource(UUIDMixin,Base):
 __tablename__="message_sources"
 message_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("messages.id",ondelete="CASCADE"),index=True);document_id:Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True),ForeignKey("documents.id",ondelete="SET NULL"),nullable=True);document_chunk_id:Mapped[UUID|None]=mapped_column(PGUUID(as_uuid=True),ForeignKey("document_chunks.id",ondelete="SET NULL"),nullable=True);document_name:Mapped[str]=mapped_column(String(255));page:Mapped[int|None]=mapped_column(Integer,nullable=True);rank:Mapped[int]=mapped_column(Integer);score:Mapped[float]=mapped_column();created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
