from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Literal, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="fastapi-app", validation_alias="APP_NAME")
    environment: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        validation_alias="ENVIRONMENT",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")
    workers: int = Field(default=1, validation_alias="WORKERS")
    reload: bool = Field(default=False, validation_alias="RELOAD")

    api_prefix: str = Field(default="/api", validation_alias="API_PREFIX")
    docs_url: Optional[str] = Field(default="/docs", validation_alias="DOCS_URL")
    redoc_url: Optional[str] = Field(default="/redoc", validation_alias="REDOC_URL")
    openapi_url: Optional[str] = Field(default="/openapi.json", validation_alias="OPENAPI_URL")

    cors_allow_origins: list[str] = Field(default_factory=list, validation_alias="CORS_ALLOW_ORIGINS")
    cors_allow_credentials: bool = Field(default=True, validation_alias="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["*"], validation_alias="CORS_ALLOW_METHODS")
    cors_allow_headers: list[str] = Field(default_factory=lambda: ["*"], validation_alias="CORS_ALLOW_HEADERS")

    def is_production(self) -> bool:
        """Return True if running in production mode."""
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def configure_logging(settings: Settings) -> None:
    """Configure application logging."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: Literal["ok"] = "ok"
    app: str
    environment: str


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
    )

    if settings.cors_allow_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
        )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(app=settings.app_name, environment=settings.environment)

    return app


app = create_app()


def _env_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce_settings_from_env() -> None:
    settings = get_settings()
    if "RELOAD" not in os.environ and settings.environment in {"development", "test"}:
        os.environ["RELOAD"] = "true"
    if "LOG_LEVEL" not in os.environ and settings.environment in {"development", "test"}:
        os.environ["LOG_LEVEL"] = "DEBUG"


_coerce_settings_from_env()


def main() -> None:
    """Run the application with Uvicorn."""
    import uvicorn

    settings = get_settings()
    reload_value = os.getenv("RELOAD")
    reload_enabled = settings.reload if reload_value is None else _env_truthy(reload_value)

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers if not reload_enabled else 1,
        reload=reload_enabled,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()