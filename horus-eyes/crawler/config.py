from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class CrawlerSettings(BaseSettings):
    PROJECT_NAME: str = "HorusEyes AI Crawler"
    
    # DB & Redis
    POSTGRES_USER: str = "horus"
    POSTGRES_PASSWORD: str = "horus_secret"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "horus"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = "horus_redis"

    # LLM Settings for AI Parsing (GPU2 Dual 5070 Ti)
    DEFAULT_LLM_PROVIDER: str = "gpu2"  # "gpu2", "ollama", "gemini"
    ENABLE_OLLAMA_FALLBACK: bool = False

    GPU2_BASE_URL: str = "http://gpu2:8000/v1"
    GPU2_MODEL: str = "qwen3.8:27b"
    GPU2_MAX_RETRIES: int = 3
    GPU2_RETRY_BACKOFF: float = 1.5
    DEFAULT_CONCURRENCY: int = 8
    MAX_TEXT_CONCURRENCY: int = 8
    MAX_VISION_CONCURRENCY: int = 4

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_URL: Optional[str] = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:35b-mlx"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Crawler Tuning
    USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    MAX_CONCURRENCY: int = 5
    REQUEST_TIMEOUT: float = 20.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

config = CrawlerSettings()
