from uuid import uuid4
import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.db.base import Base
from app.models.user import User
from app.models.conversation import MessageRole
from app.schemas.conversation import ChatRequest,ConversationCreate
from app.services.conversation_service import ConversationService

@pytest_asyncio.fixture
async def db():
 engine=create_async_engine("sqlite+aiosqlite:///:memory:")
 async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
 maker=async_sessionmaker(engine,expire_on_commit=False)
 async with maker() as session:yield session
 await engine.dispose()

@pytest_asyncio.fixture
async def users(db):
 one=User(name="One User",email="one@example.com",password_hash="x");two=User(name="Two User",email="two@example.com",password_hash="x");db.add_all([one,two]);await db.commit();return one,two

@pytest.mark.asyncio
async def test_create_list_messages_delete_and_ownership(db,users,monkeypatch):
 one,two=users;monkeypatch.setattr("app.core.config.settings.default_llm_model","test-model")
 service=ConversationService(db);conversation=await service.create(one,ConversationCreate())
 items,total=await service.repo.list(one.id,1,20);assert total==1 and items[0].id==conversation.id
 message=await service.messages.create(conversation.id,MessageRole.user,"hello");await db.commit()
 assert (await service.messages.list(conversation.id))[0].id==message.id
 with pytest.raises(HTTPException) as denied:await service.require(conversation.id,two)
 assert denied.value.status_code==404
 await service.repo.delete(conversation);await db.commit();assert await service.repo.owned(conversation.id,one.id) is None

def test_empty_chat_message_rejected():
 with pytest.raises(ValidationError):ChatRequest(conversation_id=uuid4(),message="")

def test_missing_llm_configuration(monkeypatch):
 from app.ai.llm.groq_provider import GroqProvider
 monkeypatch.setattr("app.core.config.settings.groq_api_key","");assert GroqProvider().configured is False
