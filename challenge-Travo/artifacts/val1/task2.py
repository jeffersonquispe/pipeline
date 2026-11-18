from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    api_key: str = Field(default_factory=lambda: os.getenv("API_KEY", ""))
    request_id_header: str = Field(default_factory=lambda: os.getenv("REQUEST_ID_HEADER", "X-Request-ID"))
    rate_limit_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "120")))
    rate_limit_burst: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_BURST", "20")))
    max_body_bytes: int = Field(default_factory=lambda: int(os.getenv("MAX_BODY_BYTES", "262144")))

    @field_validator("rate_limit_per_minute", "rate_limit_burst", "max_body_bytes")
    @classmethod
    def _non_negative_int(cls, v: int) -> int:
        if v < 0:
            raise ValueError("must be non-negative")
        return v


SETTINGS = Settings()


class CoreRequest(BaseModel):
    """Input payload for core logic execution."""

    action: str = Field(..., min_length=1, max_length=64)
    payload: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)

    @field_validator("action")
    @classmethod
    def _action_normalize(cls, v: str) -> str:
        return v.strip()


class CoreResponse(BaseModel):
    """Output payload for core logic execution."""

    request_id: str
    action: str
    result: Dict[str, Any]
    meta: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class TokenBucket:
    capacity: int
    refill_rate_per_sec: float
    tokens: float
    last_refill: float


class InMemoryRateLimiter:
    """Simple in-memory token bucket rate limiter keyed by a string."""

    def __init__(self, per_minute: int, burst: int) -> None:
        self._per_minute = per_minute
        self._burst = burst
        self._buckets: Dict[str, TokenBucket] = {}

    def allow(self, key: str) -> Tuple[bool, Dict[str, str]]:
        now = time.time()
        if self._per_minute <= 0:
            return True, {}

        refill_rate = self._per_minute / 60.0
        capacity = max(self._burst, 1)
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(
                capacity=capacity,
                refill_rate_per_sec=refill_rate,
                tokens=float(capacity),
                last_refill=now,
            )
            self._buckets[key] = bucket

        elapsed = max(0.0, now - bucket.last_refill)
        bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.refill_rate_per_sec)
        bucket.last_refill = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, self._headers(bucket)

        return False, self._headers(bucket)

    def _headers(self, bucket: TokenBucket) -> Dict[str, str]:
        remaining = max(0, int(bucket.tokens))
        retry_after = "1"
        if bucket.tokens < 1.0 and bucket.refill_rate_per_sec > 0:
            retry_after = str(max(1, int((1.0 - bucket.tokens) / bucket.refill_rate_per_sec)))
        return {
            "X-RateLimit-Limit": str(self._per_minute),
            "X-RateLimit-Remaining": str(remaining),
            "Retry-After": retry_after,
        }


class IdempotencyStore:
    """In-memory idempotency store. Not suitable for multi-instance deployments."""

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[float, CoreResponse]] = {}

    def get(self, key: str) -> Optional[CoreResponse]:
        item = self._store.get(key)
        if item is None:
            return None
        return item[1]

    def set(self, key: str, value: CoreResponse, ttl_sec: int = 3600) -> None:
        self._store[key] = (time.time() + ttl_sec, value)

    def gc(self) -> None:
        now = time.time()
        expired: List[str] = [k for k, (exp, _) in self._store.items() if exp <= now]
        for k in expired:
            self._store.pop(k, None)


class CoreLogic:
    """Core logic dispatcher."""

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if action == "echo":
            return {"echo": payload}
        if action == "sum":
            numbers = payload.get("numbers")
            if not isinstance(numbers, list) or not all(isinstance(x, (int, float)) for x in numbers):
                raise ValueError("payload.numbers must be a list of numbers")
            return {"sum": float(sum(numbers))}
        if action == "health":
            return {"status": "ok"}
        raise KeyError(f"unknown action: {action}")


rate_limiter = InMemoryRateLimiter(
    per_minute=SETTINGS.rate_limit_per_minute,
    burst=SETTINGS.rate_limit_burst,
)
idempotency_store = IdempotencyStore()
core_logic = CoreLogic()


def _request_id_from_header(request_id: Optional[str]) -> str:
    if request_id and request_id.strip():
        return request_id.strip()
    return str(uuid.uuid4())


async def _enforce_max_body_size(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            length = int(content_length)
        except ValueError:
            length = 0
        if SETTINGS.max_body_bytes > 0 and length > SETTINGS.max_body_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Request body too large")

    if SETTINGS.max_body_bytes <= 0:
        return

    body = await request.body()
    if len(body) > SETTINGS.max_body_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Request body too large")


def _require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    if not SETTINGS.api_key:
        return
    if x_api_key != SETTINGS.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


app = FastAPI(title="task2", version="1.0.0")


@app.middleware("http")
async def request_context_middleware(request: Request, call_next) -> Response:
    await _enforce_max_body_size(request)

    request_id = _request_id_from_header(request.headers.get(SETTINGS.request_id_header))
    request.state.request_id = request_id

    client_host = request.client.host if request.client else "unknown"
    allowed, rl_headers = rate_limiter.allow(client_host)
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"request_id": request_id, "detail": "Rate limit exceeded"},
            headers={SETTINGS.request_id_header: request_id, **rl_headers},
        )

    response = await call_next(request)
    response.headers[SETTINGS.request_id_header] = request_id
    for k, v in rl_headers.items():
        response.headers.setdefault(k, v)
    return response


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"request_id": request_id, "detail": str(exc)},
        headers={SETTINGS.request_id_header: request_id},
    )


@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    msg = str(exc).strip('"')
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"request_id": request_id, "detail": msg},
        headers={SETTINGS.request_id_header: request_id},
    )


@app.get("/health", response_model=CoreResponse)
async def health(request: Request) -> CoreResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    result = core_logic.execute("health", {})
    return CoreResponse(request_id=request_id, action="health", result=result, meta={"ts": time.time()})


@app.post("/core", response_model=CoreResponse, dependencies=[Depends(_require_api_key)])
async def core(request: Request, body: CoreRequest) -> CoreResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    idempotency_store.gc()

    if body.idempotency_key:
        cached = idempotency_store.get(body.idempotency_key)
        if cached is not None:
            cached.request_id = request_id
            return cached