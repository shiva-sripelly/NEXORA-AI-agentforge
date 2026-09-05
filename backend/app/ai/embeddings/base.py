from abc import ABC,abstractmethod
class BaseEmbeddingProvider(ABC):
 @property
 @abstractmethod
 def dimension(self)->int:...
 @abstractmethod
 async def embed_texts(self,texts:list[str])->list[list[float]]:...
 async def embed_text(self,text:str)->list[float]:return (await self.embed_texts([text]))[0]
 async def health_check(self):return {"dimension":self.dimension,"status":"available"}
