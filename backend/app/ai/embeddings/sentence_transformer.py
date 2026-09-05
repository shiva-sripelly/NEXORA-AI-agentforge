import asyncio
from functools import lru_cache
from app.ai.embeddings.base import BaseEmbeddingProvider
from app.core.config import settings
@lru_cache(maxsize=2)
def load_model(name:str):
 from sentence_transformers import SentenceTransformer
 return SentenceTransformer(name)
class SentenceTransformerProvider(BaseEmbeddingProvider):
 @property
 def dimension(self):return settings.embedding_dimension
 async def embed_texts(self,texts):
  model=await asyncio.to_thread(load_model,settings.default_embedding_model)
  vectors=await asyncio.to_thread(model.encode,texts,normalize_embeddings=True,show_progress_bar=False)
  return vectors.tolist()
