"""Application configuration, loaded from environment variables.

See specs/DEVOPS.md §3 for the authoritative list of variables and defaults.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    environment: str = "development"
    log_level: str = "INFO"
    enable_docs: bool = True

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_knowledge_assistant"
    )

    # --- Auth ---
    jwt_secret_key: str = Field(default="CHANGE_ME_IN_ENV")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # --- CORS ---
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # --- OpenAI / RAG ---
    openai_api_key: str = Field(default="")
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.2

    # --- Provider overrides (see specs/TECHNOLOGIES.md - EmbeddingProvider
    # and LLMProvider are swappable ports; these let either point at any
    # OpenAI-compatible endpoint, e.g. OpenRouter, independently of each
    # other. An unset `*_api_key` falls back to `openai_api_key`; an unset
    # `*_base_url` falls back to the OpenAI SDK's default.
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None

    # --- Retrieval (see specs/RAG_PIPELINE.md §3) ---
    chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_top_k: int = 5
    retrieval_top_k_max: int = 10
    relevance_threshold: float = 0.75

    # --- Uploads ---
    max_upload_size_mb: int = 20
    upload_storage_path: str = "/data/uploads"
    allowed_upload_extensions: list[str] = Field(default_factory=lambda: [".pdf", ".txt"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
