"""FastAPI application entrypoint.

Wires middleware, exception handlers, lifecycle (Redis/DB), and versioned
routes. The `exception_handlers` below keep error responses in the single
{ "error": {...} } envelope and never leak internals to clients.
"""

from __future__ import annotations

import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pricepilot import __version__
from pricepilot.config import settings
from pricepilot.errors import ErrorCode, PricePilotError
from pricepilot.logging import get_logger
from pricepilot.middleware import RequestIDMiddleware
from pricepilot.rate_limit import RateLimiter
from pricepilot.services.search import SearchService
from pricepilot.services.shopping import ShoppingAgentService

log = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    redis = None
    try:
        import redis.asyncio as redis_ai

        redis = redis_ai.from_url(settings.redis_url, decode_responses=True)
        await redis.ping()
        log.info("redis connected: %s", settings.redis_url.split("@")[-1])
    except Exception:
        log.warning("redis unavailable at startup; rate limiting disabled")

    app.state.redis = redis
    app.state.rate_limiter = RateLimiter(redis)
    app.state.search_service = SearchService(cache=redis)
    app.state.shopping_service = ShoppingAgentService()

    yield

    # --- shutdown ---
    await app.state.search_service.close()
    if redis is not None:
        with contextlib.suppress(Exception):
            await redis.aclose()


app = FastAPI(
    title="PricePilot API",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.exception_handler(PricePilotError)
async def pricepilot_error_handler(request: Request, exc: PricePilotError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.to_dict()},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = exc.errors()
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": ErrorCode.VALIDATION_ERROR.value,
                "message": "Request validation failed.",
                "details": details,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    log.exception("unhandled exception on %s %s", request.method, request.url.path)
    error = PricePilotError(ErrorCode.INTERNAL_ERROR, "Internal server error.")
    return JSONResponse(status_code=500, content={"error": error.to_dict()})


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)
app.add_middleware(RequestIDMiddleware)


# Import routes (routes depend on `app.state`; they register themselves).
from pricepilot.api.health import router as health_router  # noqa: E402
from pricepilot.api.v1 import routes as v1_routes  # noqa: E402

app.include_router(v1_routes.router, prefix=settings.api_prefix)
app.include_router(health_router)