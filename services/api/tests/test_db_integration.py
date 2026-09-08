"""Integration test: migrations apply and key tables/indexes exist.

Requires a live Postgres (local dev / compose). Skipped when the DB is absent
(e.g., pure-unit CI) via environment marker.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_DB_TESTS") == "1",
    reason="DB integration tests explicitly disabled",
)


def _conn():
    import asyncpg

    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://pricepilot:pricepilot@localhost:5432/pricepilot",
    )
    # asyncpg wants postgresql:// scheme
    dsn = url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")
    return asyncpg.connect(dsn)


async def test_core_tables_exist() -> None:
    conn = await _conn()
    try:
        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
        names = {r["tablename"] for r in rows}
        required = {
            "users",
            "profiles",
            "user_preferences",
            "products",
            "product_identifiers",
            "merchants",
            "sellers",
            "product_offers",
            "prices",
            "reviews",
            "review_summaries",
            "search_sessions",
            "agent_runs",
            "agent_events",
            "watchlists",
            "price_alerts",
            "notifications",
            "shopping_sessions",
            "product_embeddings",
        }
        missing = required - names
        assert not missing, f"missing tables: {sorted(missing)}"
    finally:
        await conn.close()


async def test_product_embeddings_has_hnsw_index() -> None:
    conn = await _conn()
    try:
        # vector extension must be present
        ext = await conn.fetchrow(
            "SELECT extname FROM pg_extension WHERE extname='vector'"
        )
        assert ext is not None, "pgvector extension missing"
        # HNSW index on embeddings
        idx = await conn.fetchrow(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename='product_embeddings' AND indexname='ix_product_embeddings_vec'"
        )
        assert idx is not None and "hnsw" in idx["indexdef"].lower()
    finally:
        await conn.close()


async def test_rls_enabled_on_user_tables() -> None:
    conn = await _conn()
    try:
        rows = await conn.fetch(
            "SELECT relname, relrowsecurity FROM pg_class WHERE relname IN "
            "('profiles','watchlists','price_alerts')"
        )
        by_name = {r["relname"]: r["relrowsecurity"] for r in rows}
        assert by_name == {"profiles": True, "watchlists": True, "price_alerts": True}
    finally:
        await conn.close()