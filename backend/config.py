from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/nexus_etl"
    sync_database_url: str = "postgresql+psycopg2://postgres:password@localhost:5432/nexus_etl"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Qwen (OpenAI-compatible)
    qwen_api_key: str = ""
    qwen_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-long"
    qwen_vision_model: str = "qwen-vl-max"

    # Embeddings
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1536

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Storage
    upload_dir: str = "./uploads"

    # App
    app_env: str = "development"
    secret_key: str = "dev-secret-key"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
