from uuid import UUID
from fastapi import APIRouter,File,Query,Response,UploadFile
from app.api.dependencies import CurrentUser,Db
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentList,DocumentOut
from app.services.document_service import DocumentService
router=APIRouter(prefix="/documents",tags=["Documents"])
@router.post("",response_model=DocumentOut,status_code=201)
async def upload(user:CurrentUser,db:Db,file:UploadFile=File(...)):return await DocumentService(db).upload(user,file)
@router.get("",response_model=DocumentList)
async def list_all(user:CurrentUser,db:Db,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
 items,total=await DocumentRepository(db).list(user.id,page,page_size);return DocumentList(items=items,total=total,page=page,page_size=page_size)
@router.get("/{document_id}",response_model=DocumentOut)
async def get(document_id:UUID,user:CurrentUser,db:Db):return await DocumentService(db).require(document_id,user)
@router.delete("/{document_id}",status_code=204)
async def delete(document_id:UUID,user:CurrentUser,db:Db):
 service=DocumentService(db);await service.delete(await service.require(document_id,user));return Response(status_code=204)
