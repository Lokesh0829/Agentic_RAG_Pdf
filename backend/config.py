"""
config.py — Application settings loaded from .env
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    model: str = "llama-3.3-70b-versatile"
    groq_api_key: str = ""
    embed_model: str = "all-MiniLM-L6-v2"

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "agentic_rag_pdf"

    # ChromaDB
    chroma_path: str = "./chroma_db"

    # JWT
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days

    # File Upload
    max_upload_size_mb: int = 2048
    upload_dir: str = "./uploads"

    # Semantic Cache
    cache_similarity_threshold: float = 0.95
    cache_ttl_days: int = 30

    # App
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def groq_key(self) -> str:
        return self.groq_api_key


@lru_cache()
def get_settings() -> Settings:
    import os
    settings = Settings()
    key = settings.groq_api_key
    if key:
        os.environ["GROQ_API_KEY"] = key
    return settings
