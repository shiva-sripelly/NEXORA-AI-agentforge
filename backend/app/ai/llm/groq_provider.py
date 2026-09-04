import json
from collections.abc import AsyncIterator
import httpx
from app.ai.llm.base import BaseLLMProvider,LLMMessage
from app.core.config import settings

class GroqProvider(BaseLLMProvider):
 @property
 def configured(self):return bool(settings.groq_api_key and settings.default_llm_model)
 async def stream(self,messages:list[LLMMessage],model:str)->AsyncIterator[str]:
  headers={"Authorization":f"Bearer {settings.groq_api_key}","Content-Type":"application/json"}
  payload={"model":model,"messages":messages,"stream":True}
  async with httpx.AsyncClient(timeout=60) as client:
   async with client.stream("POST","https://api.groq.com/openai/v1/chat/completions",headers=headers,json=payload) as response:
    response.raise_for_status()
    async for line in response.aiter_lines():
     if not line.startswith("data: "):continue
     raw=line[6:]
     if raw=="[DONE]":break
     chunk=json.loads(raw).get("choices",[{}])[0].get("delta",{}).get("content")
     if chunk:yield chunk
