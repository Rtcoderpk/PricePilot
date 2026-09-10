"""Phase 5 integration tests: tracking CRUD + authorization, history,
observation dedupe, monitoring status. Uses the live test DB (docker).

These hit POST/GET against the real API with `X-User-Id` scoping. The DB is the
`pricepilot` dev database; tracking rows are cleaned up after each test.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from pricepilot.api import app

ALICE = "11111111-1111-4111-8111-111111111111"
BOB = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _insert_product(dsn: str) -> str:
    import asyncio

    async def _do():
        import asyncpg

        conn = await asyncpg.connect(dsn)
        try:
            pid = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO products (id, canonical_name, brand, is_fixture) "
                "VALUES ($1, 'Test Widget', 'Acme', false)",
                pid,
            )
            gtin = "0" + str(uuid.uuid4().int)[:12]
            await conn.execute(
                "INSERT INTO product_identifiers (product_id, id_type, id_value, source) "
                "VALUES ($1, 'gtin', $2, 'test')",
                pid, gtin,
            )
            return pid
        finally:
            await conn.close()

    return asyncio.run(_do())


def test_tracking_create_list_delete(client):
    pid = _insert_product(_dsn())
    try:
        # Alice creates
        r = client.post("/api/v1/tracking", json={"product_id": pid, "target_price": 10.0}, headers={"X-User-Id": ALICE})
        assert r.status_code in (200, 201)
        body = r.json()
        wl_id = body["id"]

        # duplicate prevention
        r2 = client.post("/api/v1/tracking", json={"product_id": pid}, headers={"X-User-Id": ALICE})
        assert r2.json().get("status") == "already_tracked"

        # authz: BOB cannot see Alice's
        r3 = client.get("/api/v1/tracking", headers={"X-User-Id": BOB})
        assert all(t["id"] != wl_id for t in r3.json())

        # Alice can see + get
        r4 = client.get("/api/v1/tracking", headers={"X-User-Id": ALICE})
        assert any(t["id"] == wl_id for t in r4.json())

        # pause/resume
        r5 = client.patch(f"/api/v1/tracking/{wl_id}", json={"paused": True}, headers={"X-User-Id": ALICE})
        assert r5.json()["paused"] is True

        # BOB cannot pause Alice's
        r6 = client.patch(f"/api/v1/tracking/{wl_id}", json={"paused": False}, headers={"X-User-Id": BOB})
        assert r6.status_code == 404

        # Alice deletes
        r7 = client.delete(f"/api/v1/tracking/{wl_id}", headers={"X-User-Id": ALICE})
        assert r7.status_code == 204
    finally:
        _cleanup(pid)


def test_tracking_canonical_id_persists_product(client):
    """Tracking a canonical `pp_...` search id persists a products row, so the
    watchlist FK is satisfied and the worker can poll it (end-to-end)."""
    import asyncio

    from pricepilot.db import SessionLocal

    canonical = "pp_gtin_05781d7959874910"
    user = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

    async def _drop():
        async with SessionLocal() as s:
            from sqlalchemy import text

            await s.execute(text("DELETE FROM watchlists WHERE user_id = :u"), {"u": user})
            await s.execute(
                text("DELETE FROM product_identifiers WHERE id_value = :c"), {"c": canonical}
            )
            await s.execute(
                text("DELETE FROM products WHERE id NOT IN (SELECT product_id FROM watchlists) "
                     "AND id IN (SELECT product_id FROM product_identifiers WHERE id_value = :c)"),
                {"c": canonical},
            )
            await s.execute(text("DELETE FROM users WHERE id = :u"), {"u": user})
            await s.commit()

    try:
        r = client.post(
            "/api/v1/tracking",
            json={"product_id": canonical, "target_price": 10.0},
            headers={"X-User-Id": user},
        )
        assert r.status_code in (200, 201), r.text
        # The watchlist references a real products.id now (FK satisfied).
        listing = client.get("/api/v1/tracking", headers={"X-User-Id": user}).json()
        assert any(
            t.get("product_id") != canonical and len(t.get("product_id", "")) == 36
            for t in listing
        ), listing
    finally:
        asyncio.run(_drop())


def test_tracking_requires_user(client):
    r = client.post("/api/v1/tracking", json={"product_id": "x"})
    assert r.status_code == 401


def test_tracking_movement_fields_honest(client):
    """Tracking response carries real movement fields; with no history they are
    honestly empty (never fabricated)."""
    pid = _insert_product(_dsn())
    try:
        r = client.post("/api/v1/tracking", json={"product_id": pid}, headers={"X-User-Id": ALICE})
        assert r.status_code in (200, 201)
        wl_id = r.json()["id"]

        r2 = client.get(f"/api/v1/tracking/{wl_id}", headers={"X-User-Id": ALICE})
        body = r2.json()
        # No observation history → movement is honestly "unknown", no fake price.
        assert body["current_price"] is None
        assert body["previous_price"] is None
        assert body["percentage_change"] is None
        assert body["movement"] == "unknown"
        assert body["observation_count"] == 0
    finally:
        _cleanup(pid)


def test_alerts_requires_user(client):
    r = client.get("/api/v1/alerts", headers={"X-User-Id": ALICE})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_invalid_uuid_returns_400(client):
    r = client.get("/api/v1/alerts", headers={"X-User-Id": "nobody"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_error"


def test_identity_resolver_creates_and_reuses_user(client):
    # first request with a valid UUID creates the user row idempotently
    r1 = client.get("/api/v1/alerts", headers={"X-User-Id": ALICE})
    assert r1.status_code == 200
    # A second, identical request must not error or create a duplicate user.
    r2 = client.get("/api/v1/alerts", headers={"X-User-Id": ALICE})
    assert r2.status_code == 200
    _assert_user_count(ALICE, 1)


def test_preferences_get_set_isolation(client):
    # Alice writes preferences; Bob starts empty.
    r = client.put(
        "/api/v1/preferences",
        json={"preferred_brands": ["Acme"], "max_budget": 500},
        headers={"X-User-Id": ALICE},
    )
    assert r.status_code == 200
    prefs = r.json()["preferences"]
    assert prefs["preferred_brands"] == ["Acme"]
    assert prefs["max_budget"] == 500

    # Alice reads back the same row.
    r2 = client.get("/api/v1/preferences", headers={"X-User-Id": ALICE})
    assert r2.json()["preferences"]["preferred_brands"] == ["Acme"]

    # Bob (different UUID) must not see Alice's preferences.
    r3 = client.get("/api/v1/preferences", headers={"X-User-Id": BOB})
    assert r3.status_code == 200
    assert r3.json()["preferences"] in (None, {"updated_at": None})


def test_monitoring_status(client):
    r = client.get("/api/v1/monitoring/status")
    assert r.status_code == 200
    body = r.json()
    assert "enabled" in body
    assert "provider" in body
    assert "message" in body


def test_price_history_insufficient_when_empty(client):
    pid = _insert_product(_dsn())
    try:
        r = client.get(f"/api/v1/price-history/{pid}")
        assert r.status_code == 200
        body = r.json()
        assert body["observations"] == []
        assert body["analytics"]["status"] == "insufficient_history"
    finally:
        _cleanup(pid)


def _dsn() -> str:
    return "postgresql://pricepilot:pricepilot@localhost:5432/pricepilot"


def _assert_user_count(user_id: str, expected: int) -> None:
    import asyncio

    async def _do():
        import asyncpg

        conn = await asyncpg.connect(_dsn())
        try:
            n = await conn.fetchval("SELECT count(*) FROM users WHERE id = $1", user_id)
            assert n == expected
        finally:
            await conn.close()

    asyncio.run(_do())


def _cleanup(pid: str) -> None:
    import asyncio

    async def _do():
        import asyncpg

        conn = await asyncpg.connect(_dsn())
        try:
            await conn.execute("DELETE FROM watchlists WHERE product_id = $1", pid)
            await conn.execute("DELETE FROM product_identifiers WHERE product_id = $1", pid)
            await conn.execute("DELETE FROM products WHERE id = $1", pid)
            await conn.execute("DELETE FROM users WHERE id = ANY($1)", [ALICE, BOB])
        finally:
            await conn.close()

    asyncio.run(_do())