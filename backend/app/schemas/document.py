from datetime import datetime
from uuid import UUID
from pydantic import BaseModel,ConfigDict
from app.models.document import DocumentStatus
class DocumentOut(BaseModel):
 id:UUID;original_filename:str;display_name:str;content_type:str;file_size:int;status:DocumentStatus;processing_error:str|None;chunk_count:int;created_at:datetime;updated_at:datetime
 model_config=ConfigDict(from_attributes=True)
class DocumentList(BaseModel):items:list[DocumentOut];total:int;page:int;page_size:int
class SourceOut(BaseModel):
 document_id:UUID|None;document_chunk_id:UUID|None;document_name:str;page:int|None;rank:int;score:float
 model_config=ConfigDict(from_attributes=True)
