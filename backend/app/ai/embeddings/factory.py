from app.ai.embeddings.sentence_transformer import SentenceTransformerProvider
from app.core.config import settings
def get_embedding_provider():
 if settings.default_embedding_provider=="sentence_transformers":return SentenceTransformerProvider()
 raise RuntimeError("Embedding provider unavailable")
