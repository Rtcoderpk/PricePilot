"""Version 1 API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pricepilot.errors import ErrorCode, PricePilotError
from pricepilot.logging import get_logger
from pricepilot.models import (
    SearchQuery,
    SearchResponse,
    ShoppingSearchQuery,
    ShoppingSearchResponse,
)

if TYPE_CHECKING:
    from pricepilot.rate_limit import RateLimiter
    from pricepilot.services.search import SearchService
    from pricepilot.services.shopping import ShoppingAgentService

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


@router.post(
    "/shopping/search",
    response_model=ShoppingSearchResponse,
    summary="Run the AI shopping agent",
    description="Parses intent, searches providers, canonicalizes products, analyzes price/seller/deal, and ranks recommendations.",
)
async def shopping_search(request: Request, body: ShoppingSearchQuery) -> JSONResponse:
    limiter = _rate_limiter(request)
    allowed, _ = await limiter.check_or_increment(
        f"shopping:{_client_key(request)}",
        limit=20,
        window_seconds=60,
    )
    if not allowed:
        raise RateLimitExceededError()

    request_id = request.scope.get("request_id") or "req-unknown"
    service: ShoppingAgentService = request.app.state.shopping_service
    state = await service.run(
        request_id=request_id,
        query=body.query,
        user_id=None,
        use_llm=body.use_llm,
    )
    resp = _shopping_response(request_id, state)
    return JSONResponse(content=resp.model_dump(mode="json"))


@router.post(
    "/shopping/chat",
    response_model=ShoppingSearchResponse,
    summary="AI shopping chat (reserved)",
    description="Multi-turn shopping conversation. Not implemented yet — returns a controlled placeholder.",
)
async def shopping_chat(request: Request, body: ShoppingSearchQuery) -> JSONResponse:
    request_id = request.scope.get("request_id") or "req-unknown"
    resp = ShoppingSearchResponse(
        request_id=request_id,
        query=body.query,
        status="completed",
        warnings=["Multi-turn chat is planned for Phase 4; use /shopping/search for single-turn agent research."],
        answer="Multi-turn chat is not implemented yet. Use the single-turn shopping agent search.",
    )
    return JSONResponse(content=resp.model_dump(mode="json"))


def _shopping_response(request_id: str, state) -> ShoppingSearchResponse:
    intent_data = state.intent.model_dump(mode="json") if state.intent else None

    return ShoppingSearchResponse(
        request_id=request_id,
        query=state.original_query,
        status=state.status.value,
        intent=intent_data,
        products=[p for p in state.canonical_products],
        recommendations=[r.model_dump(mode="json") for r in state.recommendations],
        price_analysis={k: v.model_dump(mode="json") for k, v in state.price_analysis.items()},
        review_analysis={k: v.model_dump(mode="json") for k, v in state.review_analysis.items()},
        seller_analysis={k: v.model_dump(mode="json") for k, v in state.seller_analysis.items()},
        deal_scores={k: (v.model_dump(mode="json") if v else {}) for k, v in state.deal_scores.items()},
        research_evidence={k: v.model_dump(mode="json") for k, v in state.research_evidence.items()},
        warnings=state.warnings,
        provider_errors=state.provider_errors,
        confidence=state.confidence,
        answer=state.final_answer,
    )