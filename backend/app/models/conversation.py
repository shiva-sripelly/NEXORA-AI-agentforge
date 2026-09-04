import enum
from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

class MessageRole(str, enum.Enum):
    user="user"; assistant="assistant"; system="system"

class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__="conversations"
    user_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("users.id",ondelete="CASCADE"),index=True)
    title:Mapped[str]=mapped_column(String(160),default="New conversation")
    model_provider:Mapped[str]=mapped_column(String(40),default="groq")
    model_name:Mapped[str]=mapped_column(String(120))
    user=relationship("User",back_populates="conversations")
    messages=relationship("Message",back_populates="conversation",cascade="all, delete-orphan",order_by="Message.created_at")

class Message(UUIDMixin, Base):
    __tablename__="messages"
    conversation_id:Mapped[UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("conversations.id",ondelete="CASCADE"),index=True)
    role:Mapped[MessageRole]=mapped_column(Enum(MessageRole,name="message_role"))
    content:Mapped[str]=mapped_column(Text)
    token_count:Mapped[int|None]=mapped_column(Integer,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)
    conversation=relationship("Conversation",back_populates="messages")
