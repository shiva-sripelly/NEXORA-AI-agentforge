from __future__ import annotations
from uuid import UUID
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document,DocumentChunk,DocumentStatus,MessageSource
class DocumentRepository:
 def __init__(self,db:AsyncSession):self.db=db
 async def owned(self,id,user_id):return await self.db.scalar(select(Document).where(Document.id==id,Document.user_id==user_id))
 async def list(self,user_id,page,size):
  q=select(Document).where(Document.user_id==user_id).order_by(Document.created_at.desc()).offset((page-1)*size).limit(size);return list((await self.db.scalars(q)).all()),await self.db.scalar(select(func.count()).select_from(Document).where(Document.user_id==user_id)) or 0
 async def validate_ready(self,ids:list[UUID],user_id):
  rows=list((await self.db.scalars(select(Document).where(Document.id.in_(ids),Document.user_id==user_id,Document.status==DocumentStatus.ready))).all())
  if len(rows)!=len(set(ids)):return None
  return rows
class ChunkRepository:
 def __init__(self,db):self.db=db
 async def search(self,user_id,document_ids,vector,limit):
  distance=DocumentChunk.embedding.cosine_distance(vector);q=select(DocumentChunk,Document.display_name,distance.label("distance")).join(Document).where(Document.user_id==user_id,Document.id.in_(document_ids),Document.status==DocumentStatus.ready).order_by(distance).limit(limit);return (await self.db.execute(q)).all()
 async def sources(self,message_id):return list((await self.db.scalars(select(MessageSource).where(MessageSource.message_id==message_id).order_by(MessageSource.rank))).all())
