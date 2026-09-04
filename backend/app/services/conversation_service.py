import re
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository,MessageRepository
from app.schemas.conversation import ConversationCreate

class ConversationService:
 def __init__(self,db:AsyncSession):self.db=db;self.repo=ConversationRepository(db);self.messages=MessageRepository(db)
 async def create(self,user:User,data:ConversationCreate):
  provider=data.model_provider or settings.default_llm_provider;model=data.model_name or settings.default_llm_model
  if not model:raise HTTPException(503,"LLM_PROVIDER_NOT_CONFIGURED")
  item=await self.repo.create(user.id,provider,model);await self.db.commit();await self.db.refresh(item);return item
 async def require(self,id:UUID,user:User):
  item=await self.repo.owned(id,user.id)
  if not item:raise HTTPException(404,"Conversation not found")
  return item
 async def title_first(self,item,text):
  if item.title=="New conversation":item.title=" ".join(re.findall(r"[\w'-]+",text)[:7]).strip().title()[:160] or "New conversation"
