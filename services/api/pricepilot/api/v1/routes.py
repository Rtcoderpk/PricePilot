"""Version 1 API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from pricepilot.db import SessionLocal
from pricepilot.errors import ErrorCode, PricePilotError
from pricepilot.logging import get_logger
from pricepilot.models import (
    AlertRead,
    ChatQuery,
    MonitoringStatusResponse,
    PriceHistoryResponse,
    SearchQuery,
    SearchResponse,
    ShoppingSearchQuery,
    ShoppingSearchResponse,
    TrackCreate,
    TrackUpdate,
    UserPreferencesUpdate,
)
from pricepilot.services.image import ImageValidationError, identify_image, validate_image

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
    resp = await _shopping_response(request_id, state)
    return JSONResponse(content=resp.model_dump(mode="json"))


@router.post(
    "/shopping/chat",
    response_model=ShoppingSearchResponse,
    summary="AI shopping chat",
    description="Multi-turn shopping conversation with session persistence and deterministic refinements.",
)
async def shopping_chat(request: Request, body: ChatQuery) -> JSONResponse:
    limiter = _rate_limiter(request)
    allowed, _ = await limiter.check_or_increment(
        f"chat:{_client_key(request)}",
        limit=30,
        window_seconds=60,
    )
    if not allowed:
        raise RateLimitExceededError()

    request_id = request.scope.get("request_id") or "req-unknown"
    from pricepilot.services.chat import run_chat

    result = await run_chat(
        request_id=request_id,
        query=body.query,
        session_id=body.session_id,
        user_id=None,
    )
    resp = ShoppingSearchResponse(
        request_id=request_id,
        query=body.query,
        status="completed",
        intent=result.get("intent"),
        products=result.get("products", []),
        recommendations=result.get("recommendations", []),
        price_analysis=result.get("price_analysis", {}),
        review_analysis=result.get("review_analysis", {}),
        seller_analysis=result.get("seller_analysis", {}),
        deal_scores=result.get("deal_scores", {}),
        sibt=result.get("sibt", {}),
        forecasts=result.get("forecasts", {}),
        warnings=result.get("warnings", []),
        confidence=result.get("confidence", 0.0),
        answer=result.get("answer"),
        session_id=result.get("session_id"),
        conversation=result.get("conversation", []),
        refinements=[{"note": result.get("refinement")}] if result.get("refinement") else [],
    )
    return JSONResponse(content=resp.model_dump(mode="json"))


@router.post(
    "/shopping/image",
    response_model=ShoppingSearchResponse,
    summary="Image shopping",
    description="Upload a product image; returns possible matches (clearly labeled) when a vision provider is configured.",
)
async def shopping_image(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008 (FastAPI dependency-injection convention)
    max_matches: int = Form(default=3),  # noqa: B008
) -> JSONResponse:
    limiter = _rate_limiter(request)
    allowed, _ = await limiter.check_or_increment(
        f"image:{_client_key(request)}",
        limit=10,
        window_seconds=60,
    )
    if not allowed:
        raise RateLimitExceededError()

    content = await file.read()
    mime = (file.content_type or "").lower()
    try:
        validate_image(mime, len(content), content)
    except ImageValidationError as exc:
        return _validation_error(str(exc))

    request_id = request.scope.get("request_id") or "req-unknown"
    matches, notice = await identify_image(content, mime)
    return JSONResponse(
        content={
            "request_id": request_id,
            "query": f"image:{file.filename or 'upload'}",
            "status": "images" if matches else "unavailable",
            "products": [],
            "warnings": [notice] if notice else [],
            "confidence": max((m.confidence for m in matches), default=0.0),
            "answer": f"Identified {len(matches)} possible match(es)." if matches else None,
            "provider_errors": [],
            "refinements": [],
        }
    )


def _validation_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": message, "details": None}},
    )


async def _shopping_response(request_id: str, state) -> ShoppingSearchResponse:
    intent_data = state.intent.model_dump(mode="json") if state.intent else None

    semantic = "available"
    try:
        if not await _semantic_available():
            semantic = "keyword"
    except Exception:
        semantic = "keyword"

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
        sibt={k: (v.model_dump(mode="json") if v else {}) for k, v in state.sibt.items()},
        forecasts={k: (v.model_dump(mode="json") if v else {}) for k, v in state.forecasts.items()},
        research_evidence={k: v.model_dump(mode="json") for k, v in state.research_evidence.items()},
        warnings=state.warnings,
        provider_errors=state.provider_errors,
        confidence=state.confidence,
        answer=state.final_answer,
        semantic=semantic,
    )


async def _semantic_available() -> bool:
    from pricepilot.services.semantic import EmbeddingService

    service = EmbeddingService()
    return await service.available()


# --------------------------------------------------------------------------- #
# Phase 5: price monitoring / tracking / alerts / history
# --------------------------------------------------------------------------- #


def _user_id(request: Request) -> str | None:
    """Current identity. Auth is deferred (Phase 1 decision); today we accept an
    explicit `X-User-Id` header. RLS + real JWT plug in here later."""
    return request.headers.get("x-user-id")


@router.get("/monitoring/status", response_model=MonitoringStatusResponse)
async def monitoring_status(request: Request) -> JSONResponse:
    async with SessionLocal() as session:
        from pricepilot.services.monitoring_api import monitoring_status as _status

        st = await _status(session)
    return JSONResponse(content=st)


@router.get("/price-history/{product_id}", response_model=PriceHistoryResponse)
async def price_history_route(request: Request, product_id: str) -> JSONResponse:
    limiter = _rate_limiter(request)
    allowed, _ = await limiter.check_or_increment(
        f"history:{_client_key(request)}", limit=60, window_seconds=60
    )
    if not allowed:
        raise RateLimitExceededError()
    async with SessionLocal() as session:
        from pricepilot.services.monitoring_api import price_history

        result = await price_history(session, product_id=product_id)
    return JSONResponse(content=result)


@router.post("/tracking", status_code=201)
async def tracking_create(request: Request, body: TrackCreate) -> JSONResponse:
    limiter = _rate_limiter(request)
    allowed, _ = await limiter.check_or_increment(
        f"tracking:{_client_key(request)}", limit=20, window_seconds=60
    )
    if not allowed:
        raise RateLimitExceededError()
    async with SessionLocal() as session:
        from pricepilot.services.identity import resolve_user_identity
        from pricepilot.services.monitoring_api import create_tracking

        uid = await resolve_user_identity(session, _user_id(request))

        result = await create_tracking(
            session, user_id=uid, product_id=body.product_id,
            target_price=body.target_price, target_currency=body.target_currency,
            alert_preferences=body.alert_preferences,
        )
    return JSONResponse(status_code=200 if result.get("status") == "already_tracked" else 201, content=result)


@router.get("/tracking")
async def tracking_list(request: Request) -> JSONResponse:
    async with SessionLocal() as session:
        from pricepilot.services.identity import resolve_user_identity
        from pricepilot.services.monitoring_api import list_tracking

        uid = await resolve_user_identity(session, _user_id(request))

        result = await list_tracking(session, user_id=uid)
    return JSONResponse(content=result)


@router.get("/tracking/{watchlist_id}")
async def tracking_get(request: Request, watchlist_id: str) -> JSONResponse:
    async with SessionLocal() as session:
        from pricepilot.services.identity import resolve_user_identity
        from pricepilot.services.monitoring_api import get_tracking

        uid = await resolve_user_identity(session, _user_id(request))

        result = await get_tracking(session, user_id=uid, watchlist_id=watchlist_id)
    if result is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Tracking record not found.", "details": None}},
        )
    return JSONResponse(content=result)


@router.patch("/tracking/{watchlist_id}")
async def tracking_update(request: Request, watchlist_id: str, body: TrackUpdate) -> JSONResponse:
    async with SessionLocal() as session:
        from pricepilot.services.identity import resolve_user_identity
        from pricepilot.services.monitoring_api import update_tracking

        uid = await resolve_user_identity(session, _user_id(request))

        result = await update_tracking(
            session, user_id=uid, watchlist_id=watchlist_id,
            target_price=body.target_price, target_currency=body.target_currency,
            alert_preferences=body.alert_preferences, paused=body.paused,
        )
    if result is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Tracking record not found.", "details": None}},
        )
    return JSONResponse(content=result)


@router.delete("/tracking/{watchlist_id}", status_code=204)
async def tracking_delete(request: Request, watchlist_id: str) -> JSONResponse:
    async with SessionLocal() as session:
        from pricepilot.services.identity import resolve_user_identity
        from pricepilot.services.monitoring_api import delete_tracking

        uid = await resolve_user_identity(session, _user_id(request))

        ok = await delete_tracking(session, user_id=uid, watchlist_id=watchlist_id)
    if not ok:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Tracking record not found.", "details": None}},
        )
    return JSONResponse(status_code=204, content=None)


@router.get("/alerts")
async def alerts_list(request: Request, unread: bool = False) -> JSONResponse:
    async with SessionLocal() as session:
        from pricepilot.services.identity import resolve_user_identity
        from pricepilot.services.monitoring_api import list_alerts

        uid = await resolve_user_identity(session, _user_id(request))

        result = await list_alerts(session, user_id=uid, only_unread=unread)
    return JSONResponse(content=result)


@router.patch("/alerts/{notification_id}")
async def alerts_update(request: Request, notification_id: str, body: AlertRead) -> JSONResponse:
    async with SessionLocal() as session:
        from pricepilot.services.identity import resolve_user_identity
        from pricepilot.services.monitoring_api import read_alert

        uid = await resolve_user_identity(session, _user_id(request))

        ok = await read_alert(session, user_id=uid, notification_id=notification_id, status=body.status)
    if not ok:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Notification not found.", "details": None}},
        )
    return JSONResponse(content={"status": "ok"})


@router.get("/preferences")
async def preferences_get(request: Request) -> JSONResponse:
    async with SessionLocal() as session:
        from pricepilot.services.identity import resolve_user_identity
        from pricepilot.services.preferences import get_preferences

        uid = await resolve_user_identity(session, _user_id(request))

        result = await get_preferences(session, user_id=uid)
    if result is None:
        # honest empty state — no row yet, but valid (user may not have set prefs)
        return JSONResponse(content={"preferences": None})
    return JSONResponse(content={"preferences": result})


@router.put("/preferences")
async def preferences_put(request: Request, body: UserPreferencesUpdate) -> JSONResponse:
    async with SessionLocal() as session:
        from pricepilot.services.identity import resolve_user_identity
        from pricepilot.services.preferences import upsert_preferences

        uid = await resolve_user_identity(session, _user_id(request))

        fields = body.model_dump(exclude_unset=True)
        result = await upsert_preferences(session, user_id=uid, fields=fields)
    return JSONResponse(content={"preferences": result})
