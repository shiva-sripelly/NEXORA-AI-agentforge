import asyncio,json,logging
import httpx
from fastapi import HTTPException
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.llm.factory import llm_factory
from app.ai.llm.base import LLMProviderResponseError
from app.ai.prompts import DEFAULT_SYSTEM_PROMPT
from app.core.config import settings
from app.models.conversation import MessageRole
from app.models.document import MessageSource
from app.ai.rag.service import RAGService
from app.models.user import User
from app.repositories.conversation_repository import MessageRepository
from app.schemas.conversation import ChatRequest
from app.services.conversation_service import ConversationService
from app.mcp.registry import ToolRegistry
from app.models.mcp import ToolCallStatus
from app.services.tool_execution_service import ToolExecutionService, arguments_summary, result_summary

log=logging.getLogger(__name__);locks:set[tuple[str,str]]=set()
def event(name,data):return f"event: {name}\ndata: {json.dumps(data)}\n\n"
class ChatService:
 def __init__(self,db:AsyncSession):self.db=db;self.conversations=ConversationService(db);self.messages=MessageRepository(db)
 async def stream(self,user:User,data:ChatRequest)->AsyncIterator[str]:
  item=await self.conversations.require(data.conversation_id,user);item_id=item.id;key=(str(user.id),str(item_id))
  if key in locks:yield event("error",{"code":"GENERATION_IN_PROGRESS","message":"A response is already generating."});return
  provider=llm_factory.get_provider(item.model_provider)
  if not provider.configured:yield event("error",{"code":"LLM_PROVIDER_NOT_CONFIGURED","message":"AI provider is not configured. Add the Groq API key to the backend environment."});return
  locks.add(key);full=""
  try:
   await self.messages.create(item.id,MessageRole.user,data.message);await self.conversations.title_first(item,data.message);await self.db.commit()
   history=await self.messages.recent(item.id,settings.max_chat_history_messages)
   sources=[];system=DEFAULT_SYSTEM_PROMPT
   if data.document_ids:
    sources=await RAGService(self.db).retrieve(user.id,data.document_ids,data.message);system+="\n\n"+RAGService(self.db).context(sources)
   registry=ToolRegistry(self.db);definitions=await registry.llm_tools(user.id)
   system+="\n\nUse available tools only when necessary. Never invent tool results or claim a tool ran unless a result is provided. Follow the exact schemas. Never reveal hidden reasoning, secrets, or connection configuration."
   if not definitions:
    system+="\n\nNo MCP tools are connected or available for this user. Do not emit, request, or simulate a tool call. If asked to use a tool, clearly say it is unavailable and that the user must connect it in Tools / MCP. Answer any parts that do not require a tool from the supplied context."
   prompt=[{"role":"system","content":system}]+[{"role":m.role.value,"content":m.content} for m in history]
   log.info("message_generation_started user_id=%s conversation_id=%s",user.id,item.id);yield event("start",{"conversation_id":str(item.id)})
   if sources:yield event("sources",{"items":[{"document_id":str(x["chunk"].document_id),"document_chunk_id":str(x["chunk"].id),"document_name":x["document_name"],"page":x["page"],"rank":x["rank"],"score":x["score"]} for x in sources]})
   choice=await provider.choose_tool(prompt,item.model_name,definitions) if definitions else None
   tool_call=None
   if choice:
    tool=await registry.by_external_name(user.id,choice.name)
    if not tool:yield event("error",{"code":"MCP_TOOL_NOT_FOUND","message":"The selected tool is unavailable."});return
    tool_call=await ToolExecutionService(self.db).execute(user,tool.id,choice.arguments,item.id)
    trace={"id":str(tool_call.id),"tool_name":tool_call.tool_name,"status":tool_call.status.value,
     "arguments_summary":arguments_summary(tool_call.arguments),"result_summary":result_summary(tool_call.tool_name,tool_call.result),
     "risk_level":tool.risk_level,"approval_id":str(tool_call.approval.id) if tool_call.approval else None}
    yield event("tool",trace)
    if tool_call.status==ToolCallStatus.awaiting_approval:
     full=f"Approval is required before I can run `{tool_call.tool_name}`. Review the pending request in Tools / MCP."
    else:
     async for chunk in provider.stream_with_tool_result(prompt,item.model_name,choice,tool_call.result or {}):
      full+=chunk;yield event("token",{"content":chunk})
   else:
    async for chunk in provider.stream(prompt,item.model_name):
     full+=chunk;yield event("token",{"content":chunk})
   if choice and tool_call and tool_call.status==ToolCallStatus.awaiting_approval:
    yield event("token",{"content":full})
   if not full.strip():
    yield event("error",{"code":"LLM_EMPTY_RESPONSE","message":"The AI provider returned an empty response."});return
   if full.strip():
    saved=await self.messages.create(item.id,MessageRole.assistant,full)
    if tool_call:tool_call.message_id=saved.id
    for x in sources:self.db.add(MessageSource(message_id=saved.id,document_id=x["chunk"].document_id,document_chunk_id=x["chunk"].id,document_name=x["document_name"],page=x["page"],rank=x["rank"],score=x["score"]))
    await self.conversations.repo.touch(item);await self.db.commit();await self.db.refresh(saved)
    yield event("complete",{"message_id":str(saved.id),"conversation_id":str(item.id),"token_count":saved.token_count})
   log.info("message_generation_completed user_id=%s conversation_id=%s",user.id,item.id)
  except asyncio.CancelledError:await self.db.rollback();log.info("message_generation_cancelled conversation_id=%s",item_id);raise
  except httpx.HTTPStatusError as exc:
   await self.db.rollback()
   status=exc.response.status_code
   code="LLM_MODEL_UNAVAILABLE" if status==404 else "LLM_AUTH_FAILED" if status in (401,403) else "LLM_RATE_LIMITED" if status==429 else "LLM_GENERATION_FAILED"
   log.warning("llm_request_failed conversation_id=%s status=%s",item_id,status)
   yield event("error",{"code":code,"message":"The AI provider could not complete the request."})
  except LLMProviderResponseError:
   await self.db.rollback();log.warning("llm_stream_invalid conversation_id=%s",item_id)
   yield event("error",{"code":"LLM_INVALID_RESPONSE","message":"The AI provider returned an invalid streamed response."})
  except HTTPException as exc:
   await self.db.rollback()
   detail=exc.detail if isinstance(exc.detail,dict) else {"code":"MCP_TOOL_EXECUTION_FAILED","message":"Tool execution failed."}
   yield event("error",{"code":detail.get("code","MCP_TOOL_EXECUTION_FAILED"),"message":detail.get("message","Tool execution failed.")})
  except Exception:await self.db.rollback();log.exception("message_generation_failed conversation_id=%s",item_id);yield event("error",{"code":"LLM_GENERATION_FAILED","message":"Unable to generate response."})
  finally:locks.discard(key)
