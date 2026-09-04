from uuid import UUID
from fastapi import APIRouter,Query,Response
from app.api.dependencies import CurrentUser,Db
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.conversation import ConversationCreate,ConversationList,ConversationOut,ConversationUpdate,MessageOut
from app.services.conversation_service import ConversationService
router=APIRouter(prefix="/conversations",tags=["Conversations"])
@router.post("",response_model=ConversationOut,status_code=201)
async def create(data:ConversationCreate,user:CurrentUser,db:Db):return await ConversationService(db).create(user,data)
@router.get("",response_model=ConversationList)
async def list_all(user:CurrentUser,db:Db,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
 items,total=await ConversationRepository(db).list(user.id,page,page_size);return ConversationList(items=items,total=total,page=page,page_size=page_size)
@router.get("/{conversation_id}",response_model=ConversationOut)
async def get(conversation_id:UUID,user:CurrentUser,db:Db):return await ConversationService(db).require(conversation_id,user)
@router.get("/{conversation_id}/messages",response_model=list[MessageOut])
async def messages(conversation_id:UUID,user:CurrentUser,db:Db,page:int=1,page_size:int=100):
 service=ConversationService(db);item=await service.require(conversation_id,user);return await service.messages.list(item.id,page,min(page_size,100))
@router.patch("/{conversation_id}",response_model=ConversationOut)
async def rename(conversation_id:UUID,data:ConversationUpdate,user:CurrentUser,db:Db):
 item=await ConversationService(db).require(conversation_id,user);item.title=data.title.strip();await db.commit();await db.refresh(item);return item
@router.delete("/{conversation_id}",status_code=204)
async def remove(conversation_id:UUID,user:CurrentUser,db:Db):
 service=ConversationService(db);item=await service.require(conversation_id,user);await service.repo.delete(item);await db.commit();return Response(status_code=204)
