from fastapi import HTTPException
from app.ai.llm.base import BaseLLMProvider
from app.ai.llm.groq_provider import GroqProvider
class LLMProviderFactory:
 @staticmethod
 def get_provider(name:str)->BaseLLMProvider:
  if name=="groq":return GroqProvider()
  raise HTTPException(400,"Unsupported LLM provider")
llm_factory=LLMProviderFactory()
