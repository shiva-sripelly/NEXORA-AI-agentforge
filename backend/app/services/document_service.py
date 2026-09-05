import logging
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException,UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.embeddings.factory import get_embedding_provider
from app.ai.rag.chunker import chunk_parts
from app.core.config import settings
from app.models.document import Document,DocumentChunk,DocumentStatus
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.utils.documents import extract,safe_path
log=logging.getLogger(__name__);allowed={".pdf":{"application/pdf"},".txt":{"text/plain","application/octet-stream"},".md":{"text/markdown","text/plain","application/octet-stream"}}
class DocumentService:
 def __init__(self,db:AsyncSession):self.db=db;self.repo=DocumentRepository(db)
 async def upload(self,user:User,file:UploadFile):
  name=Path(file.filename or "").name;suffix=Path(name).suffix.lower()
  if suffix not in allowed or file.content_type not in allowed[suffix]:raise HTTPException(415,{"code":"UNSUPPORTED_DOCUMENT_TYPE","message":"Supported file types are PDF, TXT, and Markdown."})
  data=await file.read(settings.max_document_size_mb*1024*1024+1)
  if len(data)>settings.max_document_size_mb*1024*1024:raise HTTPException(413,{"code":"DOCUMENT_TOO_LARGE","message":f"Maximum document size is {settings.max_document_size_mb} MB."})
  if suffix==".pdf" and not data.startswith(b"%PDF"):raise HTTPException(415,{"code":"UNSUPPORTED_DOCUMENT_TYPE","message":"The uploaded file is not a valid PDF."})
  doc=Document(id=uuid4(),user_id=user.id,original_filename=name,display_name=name,content_type=file.content_type or "application/octet-stream",file_size=len(data),storage_path="pending",status=DocumentStatus.processing,chunk_count=0);path=safe_path(settings.document_storage_path,user.id,doc.id,suffix);doc.storage_path=str(path);self.db.add(doc);await self.db.commit()
  try:
   path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);parts=extract(data,suffix)
   if not parts or not any(p.text for p in parts):raise ValueError("Unable to extract text from this document.")
   chunks=chunk_parts(parts,settings.rag_chunk_size,settings.rag_chunk_overlap);vectors=await get_embedding_provider().embed_texts([x[0] for x in chunks])
   self.db.add_all([DocumentChunk(document_id=doc.id,chunk_index=i,content=text,embedding=vector,metadata_json={**meta,"filename":name}) for i,((text,meta),vector) in enumerate(zip(chunks,vectors))]);doc.chunk_count=len(chunks);doc.status=DocumentStatus.ready;await self.db.commit();await self.db.refresh(doc);log.info("document_ready user_id=%s document_id=%s chunk_count=%s",user.id,doc.id,len(chunks));return doc
  except Exception:
   await self.db.rollback();stored=await self.db.get(Document,doc.id)
   if stored:stored.status=DocumentStatus.failed;stored.processing_error="Document processing failed.";await self.db.commit()
   log.exception("document_failed user_id=%s document_id=%s",user.id,doc.id);raise HTTPException(422,{"code":"DOCUMENT_PROCESSING_FAILED","message":"Document processing failed."})
 async def require(self,id,user):
  item=await self.repo.owned(id,user.id)
  if not item:raise HTTPException(404,{"code":"DOCUMENT_NOT_FOUND","message":"Document not found."})
  return item
 async def delete(self,item):
  path=Path(item.storage_path);await self.db.delete(item);await self.db.commit()
  try:path.unlink(missing_ok=True)
  except OSError:log.warning("document_file_cleanup_failed document_id=%s",item.id)
