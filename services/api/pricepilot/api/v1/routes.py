"""Version 1 API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pricepilot.errors import ErrorCode, PricePilotError
from pricepilot.logging import get_logger
from pricepilot.models import SearchQuery, SearchResponse

if TYPE_CHECKING:
    from pricepilot.rate_limit import RateLimiter
    from pricepilot.services.search import SearchService

log = get_logger("api.v1")

router = APIRouter()


def _rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class RateLimitExceededError(PricePilotError):
    def __init__(self) -> None:
        super().__init__(
            ErrorCode.RATE_LIMITED,
            "Too many requests. Slow down and retry shortly.",
            status_code=429,
        )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Run a shopping search",
    description="Searches configured providers for a natural-language query and returns normalized products.",
)
async def search(request: Request, body: SearchQuery) -> JSONResponse:
    limiter = _rate_limiter(request)
    allowed, _ = await limiter.check_or_increment(
        f"search:{_client_key(request)}",
        limit=30,
        window_seconds=60,
    )
    if not allowed:
        raise RateLimitExceededError()

    service: SearchService = request.app.state.search_service
    result: SearchResponse = await service.run_search(
        body.query,
        max_results=body.max_results,
        cache_keys=(body.query, body.max_results),
    )
    return JSONResponse(content=result.model_dump(mode="json"))