from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentForge API"
    environment: str = "development"
    app_debug: bool = False
    database_url: str = "postgresql+asyncpg://agentforge:agentforge@localhost:5432/agentforge"
    secret_key: str = Field(default="change-me-in-production-at-least-32-characters")
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = ""  # Comma-separated additional frontend origins
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    groq_api_key: str = ""
    default_llm_provider: str = "groq"
    default_llm_model: str = ""
    max_chat_history_messages: int = 20
    max_chat_message_length: int = 10000
    default_embedding_provider: str = "sentence_transformers"
    default_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    max_document_size_mb: int = 10
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_top_k: int = 5
    document_storage_path: str = "storage/documents"
    mcp_file_root: str = "storage/mcp_workspace"
    mcp_server_root: str = "mcp_servers"
    mcp_timeout_seconds: float = 15.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
