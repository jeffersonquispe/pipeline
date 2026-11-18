from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, List, Optional

from pydantic import AnyHttpUrl, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and optional .env files.

    Environment variable naming follows uppercase snake-case. The default env file
    is `.env` in the current working directory, unless overridden by `ENV_FILE`.
    """

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="FastAPI App", validation_alias="APP_NAME")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")

    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    allowed_origins: List[str] = Field(default_factory=list, validation_alias="ALLOWED_ORIGINS")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> List[str]:
        """
        Parse ALLOWED_ORIGINS from common formats.

        Supported formats:
        - JSON array string: '["https://a.com","https://b.com"]'
        - Comma-separated string: 'https://a.com, https://b.com'
        - Single string: 'https://a.com'
        - List/tuple of strings (already parsed)
        - Empty / unset: []
        """
        if value is None:
            return []

        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value if str(v).strip()]

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("[") and raw.endswith("]"):
                # Let pydantic parse JSON-like structures by returning raw string
                # only if it is not plain comma-separated.
                return raw  # type: ignore[return-value]
            parts = [p.strip() for p in raw.split(",")]
            return [p for p in parts if p]

        return [str(value).strip()] if str(value).strip() else []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return cached Settings instance (thread-safe via lru_cache).
    """
    return Settings()


def ensure_required_environment() -> Settings:
    """
    Validate environment configuration and return Settings.

    Raises:
        RuntimeError: If settings validation fails.
    """
    try:
        return get_settings()
    except ValidationError as exc:
        raise RuntimeError(f"Invalid environment configuration: {exc}") from exc


def build_cors_origins(settings: Settings) -> List[str]:
    """
    Build the final CORS origins list.

    Accepts wildcard "*" if explicitly configured.
    """
    origins = [o.strip() for o in settings.allowed_origins if o and o.strip()]
    if "*" in origins:
        return ["*"]
    return origins


def build_cors_origin_regex(settings: Settings) -> Optional[str]:
    """
    Build an optional CORS origin regex based on settings.

    Returns:
        None by default; override in settings if you need regex-based origins.
    """
    _ = settings
    return None