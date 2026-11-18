from __future__ import annotations

import logging
import logging.config
import os
from functools import lru_cache
from typing import Any, Dict, Optional

from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="APP_", case_sensitive=False)

    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="fastapi-service")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


def _build_logging_config(settings: Settings) -> Dict[str, Any]:
    """Build a dictConfig-compatible logging configuration."""
    level = settings.log_level.upper()

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            },
            "access": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": level,
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
        "loggers": {
            "uvicorn": {"level": level, "propagate": True},
            "uvicorn.error": {"level": level, "propagate": True},
            "uvicorn.access": {"level": level, "handlers": ["console"], "propagate": False},
        },
    }


def configure_logging(settings: Settings) -> None:
    """Configure application logging.

    This must be called at runtime (e.g., in an app lifespan handler) to avoid
    module import side effects and to play nicely with ASGI servers.
    """
    logging.config.dictConfig(_build_logging_config(settings))


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app_settings = settings or get_settings()

    app = FastAPI(
        title=app_settings.service_name,
        docs_url="/docs" if app_settings.environment != "production" else None,
        redoc_url="/redoc" if app_settings.environment != "production" else None,
        openapi_url="/openapi.json" if app_settings.environment != "production" else None,
    )

    @app.on_event("startup")
    def _on_startup() -> None:
        configure_logging(app_settings)
        logging.getLogger(__name__).info(
            "Starting service",
            extra={
                "service_name": app_settings.service_name,
                "environment": app_settings.environment,
            },
        )

    @app.get("/health", tags=["system"])
    def health() -> Dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    return app


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


if _is_truthy(os.getenv("APP_CREATE_APP_AT_IMPORT", "")):
    app = create_app()