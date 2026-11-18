from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and optional .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="FastAPI Service", validation_alias="APP_NAME")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = Field(default=False, validation_alias="DEBUG")

    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")

    cors_allowed_origins: str = Field(default="", validation_alias="CORS_ALLOWED_ORIGINS")

    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @property
    def allowed_origins_list(self) -> list[str]:
        """
        Return CORS allowed origins as a normalized list.

        Supports:
        - Comma-separated values: "https://a.com, https://b.com"
        - JSON-like list: '["https://a.com","https://b.com"]'
        - Wildcard: "*"
        """
        raw = self.cors_allowed_origins.strip()
        if not raw:
            return []

        if raw == "*":
            return ["*"]

        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            if not inner:
                return []
            parts = [p.strip() for p in inner.split(",")]
            return [p.strip("\"'").strip() for p in parts if p.strip("\"'").strip()]

        return [o.strip() for o in raw.split(",") if o.strip()]

    def as_exported_env(self) -> dict[str, object]:
        """
        Export a diagnostics-friendly view of configuration values.

        Secrets and sensitive values are intentionally omitted.
        """
        return {
            "app_name": self.app_name,
            "environment": self.environment,
            "debug": self.debug,
            "host": self.host,
            "port": self.port,
            "cors_allowed_origins": self.allowed_origins_list,
            "database_configured": self.database_url is not None,
            "log_level": self.log_level,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return cached Settings instance.
    """
    return Settings()