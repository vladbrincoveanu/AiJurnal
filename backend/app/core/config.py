from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Memory Journal API"
    api_key: str = "change-me"
    redis_url: str = "redis://redis:6379/0"

    postgres_user: str = "ai_journal"
    postgres_password: str = "ai_journal"
    postgres_db: str = "ai_journal"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    openai_api_key: str = ""
    openai_base_url: str = "http://localhost:1234/v1"
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def database_url_async(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
