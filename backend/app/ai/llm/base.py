from abc import ABC,abstractmethod
from collections.abc import AsyncIterator
from typing import TypedDict
class LLMMessage(TypedDict):role:str;content:str
class BaseLLMProvider(ABC):
 @property
 @abstractmethod
 def configured(self)->bool:...
 @abstractmethod
 async def stream(self,messages:list[LLMMessage],model:str)->AsyncIterator[str]:...
 async def health_check(self)->dict:return {"configured":self.configured,"status":"available" if self.configured else "not_configured"}
