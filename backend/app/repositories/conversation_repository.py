from uuid import UUID
from sqlalchemy import delete,func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import Conversation,Message,MessageRole

class ConversationRepository:
 def __init__(self,db:AsyncSession):self.db=db
 async def create(self,user_id:UUID,provider:str,model:str):
  item=Conversation(user_id=user_id,title="New conversation",model_provider=provider,model_name=model);self.db.add(item);await self.db.flush();return item
 async def owned(self,id:UUID,user_id:UUID):return await self.db.scalar(select(Conversation).where(Conversation.id==id,Conversation.user_id==user_id))
 async def list(self,user_id:UUID,page:int,size:int):
  query=select(Conversation).where(Conversation.user_id==user_id).order_by(Conversation.updated_at.desc()).offset((page-1)*size).limit(size)
  items=list((await self.db.scalars(query)).all())
  total=await self.db.scalar(select(func.count()).select_from(Conversation).where(Conversation.user_id==user_id))
  return items,total or 0
 async def delete(self,item:Conversation):await self.db.delete(item)
 async def touch(self,item:Conversation):item.updated_at=func.now();await self.db.flush()

class MessageRepository:
 def __init__(self,db:AsyncSession):self.db=db
 async def create(self,cid:UUID,role:MessageRole,content:str,tokens:int|None=None):
  item=Message(conversation_id=cid,role=role,content=content,token_count=tokens);self.db.add(item);await self.db.flush();return item
 async def list(self,cid:UUID,page:int=1,size:int=100):return list((await self.db.scalars(select(Message).where(Message.conversation_id==cid).order_by(Message.created_at).offset((page-1)*size).limit(size))).all())
 async def recent(self,cid:UUID,limit:int):
  rows=list((await self.db.scalars(select(Message).where(Message.conversation_id==cid).order_by(Message.created_at.desc()).limit(limit))).all());return list(reversed(rows))
