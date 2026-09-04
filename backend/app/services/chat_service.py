import asyncio,json,logging
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.llm.factory import llm_factory
from app.ai.prompts import DEFAULT_SYSTEM_PROMPT
from app.core.config import settings
from app.models.conversation import MessageRole
from app.models.user import User
from app.repositories.conversation_repository import MessageRepository
from app.schemas.conversation import ChatRequest
from app.services.conversation_service import ConversationService

log=logging.getLogger(__name__);locks:set[tuple[str,str]]=set()
def event(name,data):return f"event: {name}\ndata: {json.dumps(data)}\n\n"
class ChatService:
 def __init__(self,db:AsyncSession):self.db=db;self.conversations=ConversationService(db);self.messages=MessageRepository(db)
 async def stream(self,user:User,data:ChatRequest)->AsyncIterator[str]:
  item=await self.conversations.require(data.conversation_id,user);key=(str(user.id),str(item.id))
  if key in locks:yield event("error",{"code":"GENERATION_IN_PROGRESS","message":"A response is already generating."});return
  provider=llm_factory.get_provider(item.model_provider)
  if not provider.configured:yield event("error",{"code":"LLM_PROVIDER_NOT_CONFIGURED","message":"AI provider is not configured. Add the Groq API key to the backend environment."});return
  locks.add(key);full=""
  try:
   await self.messages.create(item.id,MessageRole.user,data.message);await self.conversations.title_first(item,data.message);await self.db.commit()
   history=await self.messages.recent(item.id,settings.max_chat_history_messages)
   prompt=[{"role":"system","content":DEFAULT_SYSTEM_PROMPT}]+[{"role":m.role.value,"content":m.content} for m in history]
   log.info("message_generation_started user_id=%s conversation_id=%s",user.id,item.id);yield event("start",{"conversation_id":str(item.id)})
   async for chunk in provider.stream(prompt,item.model_name):
    full+=chunk;yield event("token",{"content":chunk})
   if full.strip():
    saved=await self.messages.create(item.id,MessageRole.assistant,full);await self.conversations.repo.touch(item);await self.db.commit();await self.db.refresh(saved)
    yield event("complete",{"message_id":str(saved.id),"conversation_id":str(item.id),"token_count":saved.token_count})
   log.info("message_generation_completed user_id=%s conversation_id=%s",user.id,item.id)
  except asyncio.CancelledError:await self.db.rollback();log.info("message_generation_cancelled conversation_id=%s",item.id);raise
  except Exception:await self.db.rollback();log.exception("message_generation_failed conversation_id=%s",item.id);yield event("error",{"code":"LLM_GENERATION_FAILED","message":"Unable to generate response."})
  finally:locks.discard(key)
