"""Application settings, loaded from environment variables and the .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All configuration for the app lives here, in one typed place."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    # General
    app_name: str = "FDE Sprint API"
    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # LLM provider secrets
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    embedding_use_query_prefix: bool = True

    # Models (small, cheap models for development)
    openai_model: str = "gpt-5-nano"
    anthropic_model: str = "claude-haiku-5-5"

    # Safety limits for LLM calls
    llm_timeout_seconds: float = 30.0
    llm_max_output_tokens: int = 1000

    # Database
    database_url: SecretStr | None = None

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    embedding_query_prefix: str = (
        "Represent this sentence for searching relevant passages: "
    )
    embedding_cache_dir: Path = PROJECT_ROOT / ".cache" / "fastembed"


@lru_cache
def get_settings() -> Settings:
    """Create the Settings object once and reuse it everywhere."""
    return Settings()