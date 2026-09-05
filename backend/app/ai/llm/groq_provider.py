import json
from collections.abc import AsyncIterator
import httpx
from app.ai.llm.base import BaseLLMProvider,LLMMessage,LLMProviderResponseError,LLMToolCall
from app.core.config import settings

class GroqProvider(BaseLLMProvider):
 @property
 def configured(self):return bool(settings.groq_api_key and settings.default_llm_model)
 async def stream(self,messages:list[LLMMessage],model:str)->AsyncIterator[str]:
  headers={"Authorization":f"Bearer {settings.groq_api_key}","Content-Type":"application/json"}
  payload={"model":model,"messages":messages,"stream":True,"reasoning_effort":"low","max_completion_tokens":2048,"temperature":0.2}
  async with httpx.AsyncClient(timeout=60) as client:
   async with client.stream("POST","https://api.groq.com/openai/v1/chat/completions",headers=headers,json=payload) as response:
    response.raise_for_status()
    async for line in response.aiter_lines():
     if not line.startswith("data: "):continue
     raw=line[6:]
     if raw=="[DONE]":break
     packet=json.loads(raw)
     if packet.get("error"):
      raise LLMProviderResponseError("The AI provider returned an invalid streamed completion.")
     chunk=(packet.get("choices") or [{}])[0].get("delta",{}).get("content")
     if chunk:yield chunk
 async def choose_tool(self,messages:list[LLMMessage],model:str,tools:list[dict])->LLMToolCall|None:
  if not tools:return None
  headers={"Authorization":f"Bearer {settings.groq_api_key}","Content-Type":"application/json"}
  payload={"model":model,"messages":messages,"tools":tools,"tool_choice":"auto","stream":False,"reasoning_effort":"low","max_completion_tokens":2048,"temperature":0.2}
  async with httpx.AsyncClient(timeout=60) as client:
   response=await client.post("https://api.groq.com/openai/v1/chat/completions",headers=headers,json=payload)
   response.raise_for_status();message=response.json().get("choices",[{}])[0].get("message",{})
  calls=message.get("tool_calls") or []
  if not calls:return None
  call=calls[0];function=call.get("function",{})
  try:arguments=json.loads(function.get("arguments") or "{}")
  except json.JSONDecodeError:return None
  return LLMToolCall(id=call.get("id") or "agentforge-tool-call",name=function.get("name","")[:120],arguments=arguments)
 async def stream_with_tool_result(self,messages:list[LLMMessage],model:str,call:LLMToolCall,result:dict)->AsyncIterator[str]:
  tool_call={"id":call.id,"type":"function","function":{"name":call.name,"arguments":json.dumps(call.arguments)}}
  enriched=messages+[{"role":"assistant","content":"","tool_calls":[tool_call]},
   {"role":"tool","tool_call_id":call.id,"name":call.name,"content":json.dumps(result)}]
  async for chunk in self.stream(enriched,model):yield chunk
