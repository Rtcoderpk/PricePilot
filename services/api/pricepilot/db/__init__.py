"""Async SQLAlchemy engine and session factory.

Phase 1 wires the engine so the /health database check and future migrations
share one configuration. Models land in Phase 2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from pricepilot.config import settings
from pricepilot.logging import get_logger

log = get_logger("db")


class Base(DeclarativeBase):
    pass


# Under tests we use a NullPool: pytest-asyncio gives each test its own event
# loop, and a shared queued pool would recycle connections across loops
# (asyncpg "Event loop is closed" cascade on both Windows and CI). NullPool
# closes a connection as soon as the session ends, so nothing outlives its loop.
_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "echo": False,
}
if settings.app_env == "test":
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs.update(pool_size=5, max_overflow=10, pool_recycle=1800)

engine = create_async_engine(settings.database_url, **_engine_kwargs)

SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an async session."""
    async with SessionLocal() as session:
        yield session


async def ping_database() -> bool:
    """Cheap connectivity check used by /health and readiness probes."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        log.warning("database ping failed")
        return False