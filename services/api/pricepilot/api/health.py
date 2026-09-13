"""Liveness and readiness health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pricepilot import __version__
from pricepilot.db import ping_database
from pricepilot.logging import get_logger
from pricepilot.providers.registry import search_provider_status

log = get_logger("api.health")

router = APIRouter()


@router.get("/health", summary="Liveness probe")
async def health() -> JSONResponse:
    """200 when the process is up; does not require the DB."""
    return JSONResponse(
        content={
            "status": "ok",
            "app_version": __version__,
            "uptime_readiness_indicator": "liveness",
        }
    )


@router.get("/readyz", summary="Readiness probe")
async def readyz(request: Request) -> JSONResponse:
    """200 only when DB (essential) and Redis (degradable) are reachable."""
    db_ok = await ping_database()

    redis_ok = True
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        try:
            await redis.ping()
        except Exception:
            redis_ok = False

    status_provider = search_provider_status()
    ready = db_ok  # Redis is optional for core reads; DB is not.

    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "app_version": __version__,
            "checks": {
                "database": "ok" if db_ok else "unreachable",
                "redis": "ok" if redis_ok else "degraded",
                "search_provider": status_provider.availability.value,
            },
        },
    )


@router.get("/diagnostics", summary="Provider diagnostics")
async def diagnostics(request: Request) -> JSONResponse:
    """Detailed health and latency status for all connected providers."""
    import time
    from pricepilot.config import settings
    from pricepilot.providers.registry import search_provider_statuses

    providers_info: list[dict] = []

    # 1. Database
    t0 = time.monotonic()
    db_ok = await ping_database()
    db_lat = round((time.monotonic() - t0) * 1000, 2)
    providers_info.append({
        "provider": "database",
        "status": "ok" if db_ok else "unreachable",
        "latency_ms": db_lat,
        "error": None if db_ok else "PostgreSQL connection failed",
    })

    # 2. Redis
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        t0 = time.monotonic()
        try:
            await redis.ping()
            r_lat = round((time.monotonic() - t0) * 1000, 2)
            r_ok = True
            r_err = None
        except Exception as e:
            r_lat = 0.0
            r_ok = False
            r_err = str(e)
    else:
        r_ok = False
        r_lat = 0.0
        r_err = "Redis not configured"

    providers_info.append({
        "provider": "redis",
        "status": "ok" if r_ok else "degraded",
        "latency_ms": r_lat,
        "error": r_err,
    })

    # 3. Gemini AI
    ai_has_key = bool(settings.ai_api_key)
    providers_info.append({
        "provider": "gemini_ai",
        "status": "available" if ai_has_key else "unconfigured",
        "model": settings.ai_model or "gemini-2.5-flash",
        "latency_ms": 0.0,
        "error": None if ai_has_key else "AI_API_KEY environment variable not set",
    })

    # 4. Search Providers
    for sp in search_provider_statuses():
        providers_info.append({
            "provider": f"search_{sp.name}",
            "status": sp.availability.value,
            "latency_ms": 0.0,
            "error": sp.reason,
        })

    return JSONResponse(content={"status": "ok", "diagnostics": providers_info})