from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s - %(message)s"


def _get_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _get_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def _get_str(value: Optional[str], default: str) -> str:
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _get_list(value: Optional[str], default: list[str]) -> list[str]:
    if value is None:
        return default
    items = [item.strip() for item in value.split(",")]
    items = [item for item in items if item]
    return items if items else default


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings loaded from environment variables."""

    app_name: str
    environment: str
    debug: bool
    log_level: str

    host: str
    port: int

    cors_allow_origins: list[str]
    cors_allow_credentials: bool
    cors_allow_methods: list[str]
    cors_allow_headers: list[str]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    @property
    def effective_log_level(self) -> str:
        level = self.log_level.strip().upper()
        return level if level else ("INFO" if self.is_production else "DEBUG")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings loaded from the environment."""
    environment = _get_str(os.getenv("ENVIRONMENT"), "development")
    debug = _get_bool(os.getenv("DEBUG"), default=environment.lower() not in {"prod", "production"})

    return Settings(
        app_name=_get_str(os.getenv("APP_NAME"), "fastapi-service"),
        environment=environment,
        debug=debug,
        log_level=_get_str(os.getenv("LOG_LEVEL"), "INFO"),
        host=_get_str(os.getenv("HOST"), "0.0.0.0"),
        port=_get_int(os.getenv("PORT"), 8000),
        cors_allow_origins=_get_list(os.getenv("CORS_ALLOW_ORIGINS"), ["*"]),
        cors_allow_credentials=_get_bool(os.getenv("CORS_ALLOW_CREDENTIALS"), default=False),
        cors_allow_methods=_get_list(os.getenv("CORS_ALLOW_METHODS"), ["*"]),
        cors_allow_headers=_get_list(os.getenv("CORS_ALLOW_HEADERS"), ["*"]),
    )


def configure_logging(settings: Settings) -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=getattr(logging, settings.effective_log_level, logging.INFO),
        format=LOG_FORMAT,
    )
    logging.getLogger("uvicorn.error").setLevel(getattr(logging, settings.effective_log_level, logging.INFO))
    logging.getLogger("uvicorn.access").setLevel(getattr(logging, settings.effective_log_level, logging.INFO))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    return app


app: FastAPI = create_app()


def main() -> None:
    """Entrypoint for running the app with `python -m`."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=not settings.is_production and settings.debug,
        log_level=settings.effective_log_level.lower(),
    )


if __name__ == "__main__":
    main()