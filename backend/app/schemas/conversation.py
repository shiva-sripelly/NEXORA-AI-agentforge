from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.conversation import MessageRole
from app.schemas.document import SourceOut
from app.schemas.mcp import ToolCallOut

class ConversationCreate(BaseModel):
    model_provider:str|None=None; model_name:str|None=None
class ConversationUpdate(BaseModel):
    title:str=Field(min_length=1,max_length=160)
class ConversationOut(BaseModel):
    id:UUID; title:str; model_provider:str; model_name:str; created_at:datetime; updated_at:datetime
    model_config=ConfigDict(from_attributes=True)
class MessageOut(BaseModel):
    id:UUID; conversation_id:UUID; role:MessageRole; content:str; token_count:int|None; created_at:datetime; sources:list[SourceOut]=Field(default_factory=list); tool_calls:list[ToolCallOut]=Field(default_factory=list)
    model_config=ConfigDict(from_attributes=True)
class ConversationList(BaseModel):
    items:list[ConversationOut]; total:int; page:int; page_size:int
class ChatRequest(BaseModel):
    conversation_id:UUID; message:str=Field(min_length=1,max_length=10000); document_ids:list[UUID]=Field(default_factory=list,max_length=20)
