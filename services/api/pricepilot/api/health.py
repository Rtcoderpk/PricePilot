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