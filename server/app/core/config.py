"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_DIRECTORY = Path(__file__).resolve().parents[2]
REPOSITORY_DIRECTORY = SERVER_DIRECTORY.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_DIRECTORY / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "PolicyKit"
    app_env: Literal["development", "test", "production"] = "development"
    app_secret_key: str = "change-me-in-production"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/policykit"

    openai_api_key: str | None = None
    openai_agent_model: str = "gpt-5.4-mini"
    openai_checker_model: str = "gpt-5.4-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_store_responses: bool = False

    chroma_mode: Literal["persistent", "http", "disabled"] = "persistent"
    chroma_persist_directory: Path = REPOSITORY_DIRECTORY / ".data" / "chroma"
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_ssl: bool = False
    chroma_api_key: str | None = None
    chroma_tenant: str | None = None
    chroma_database: str | None = None

    run_agent_worker: bool = True
    agent_poll_interval_seconds: float = 1.0
    agent_max_steps: int = 12
    agent_stale_after_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
