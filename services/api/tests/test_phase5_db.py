"""Phase 5 DB integration tests: observation persistence + dedupe + analytics.

Requires the dockerized Postgres (same as other DB tests). Deterministic fixtures
are created and cleaned up; no network.
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_DB_TESTS") == "1",
    reason="DB integration tests explicitly disabled",
)

from sqlalchemy import text  # noqa: E402

from pricepilot.db import SessionLocal  # noqa: E402
from pricepilot.monitoring.analytics import compute_analytics  # noqa: E402
from pricepilot.monitoring.observe import Observation, record_observation  # noqa: E402


async def _seed_product_offer() -> tuple[str, str]:
    async with SessionLocal() as s:
        pid = str(uuid.uuid4())
        oid = str(uuid.uuid4())
        await s.execute(
            text("INSERT INTO products (id, canonical_name, brand, is_fixture) VALUES (:id, 'Obs Widget', 'Acme', false)"),
            {"id": pid},
        )
        sid = await _seed_seller(s)
        await s.execute(
            text(
                "INSERT INTO product_offers (id, product_id, seller_id, price_amount, price_currency, available) "
                "VALUES (:oid, :pid, :sid, 50.0, 'USD', true)"
            ),
            {"oid": oid, "pid": pid, "sid": sid},
        )
        await s.commit()
        return pid, oid


async def _seed_seller(s) -> str:
    mid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    await s.execute(
        text("INSERT INTO merchants (id, name, domain) VALUES (:id, 'Acme Shop', :dom)"),
        {"id": mid, "dom": f"acme-{uuid.uuid4().hex[:8]}.test"},
    )
    await s.execute(
        text("INSERT INTO sellers (id, merchant_id, name, seller_ref) VALUES (:id, :mid, 'Acme', :ref)"),
        {"id": sid, "mid": mid, "ref": f"acme-{uuid.uuid4().hex[:6]}"},
    )
    return sid


async def _cleanup(pids: list[str]) -> None:
    async with SessionLocal() as s:
        for pid in pids:
            await s.execute(text("DELETE FROM prices WHERE product_id = :p"), {"p": pid})
            await s.execute(text("DELETE FROM product_offers WHERE product_id = :p"), {"p": pid})
            await s.execute(text("DELETE FROM product_identifiers WHERE product_id = :p"), {"p": pid})
            await s.execute(text("DELETE FROM products WHERE id = :p"), {"p": pid})
        await s.commit()


async def test_observation_persist_and_dedupe():
    pid, oid = await _seed_product_offer()
    try:
        async with SessionLocal() as s:
            # first observation inserts
            r1 = await record_observation(
                s, Observation(product_id=pid, offer_id=oid, amount=50.0, currency="USD")
            )
            assert r1.inserted is True

            # unchanged within window → deduped (no duplicate row)
            r2 = await record_observation(
                s, Observation(product_id=pid, offer_id=oid, amount=50.0, currency="USD")
            )
            assert r2.inserted is False
            assert r2.reason == "unchanged_within_window"

            # changed price → new observation
            r3 = await record_observation(
                s, Observation(product_id=pid, offer_id=oid, amount=45.0, currency="USD")
            )
            assert r3.inserted is True

            # exactly 2 rows persisted
            n = (await s.execute(text("SELECT count(*) AS c FROM prices WHERE offer_id=:o"), {"o": oid})).scalar()
            assert n == 2
    finally:
        await _cleanup([pid])


async def test_observation_no_price_writes_nothing():
    pid, oid = await _seed_product_offer()
    try:
        async with SessionLocal() as s:
            r = await record_observation(
                s, Observation(product_id=pid, offer_id=oid, amount=None, currency="USD")
            )
            assert r.inserted is False
            assert r.reason == "no_price"
            # no fabricated price row
            n = (await s.execute(text("SELECT count(*) AS c FROM prices WHERE offer_id=:o"), {"o": oid})).scalar()
            assert n == 0
    finally:
        await _cleanup([pid])


async def test_analytics_insufficient_single():
    pid, oid = await _seed_product_offer()
    try:
        async with SessionLocal() as s:
            await record_observation(s, Observation(product_id=pid, offer_id=oid, amount=50.0, currency="USD"))
            a = await compute_analytics(s, pid)
            assert a.status == "insufficient_history"
            assert a.observation_count == 1
            assert a.current_price == 50.0
    finally:
        await _cleanup([pid])


async def test_analytics_available_two_observations():
    pid, oid = await _seed_product_offer()
    try:
        async with SessionLocal() as s:
            await record_observation(s, Observation(product_id=pid, offer_id=oid, amount=50.0, currency="USD"))
            await record_observation(s, Observation(product_id=pid, offer_id=oid, amount=45.0, currency="USD"))
            a = await compute_analytics(s, pid)
            assert a.status == "available"
            assert a.observation_count == 2
            assert a.current_price == 45.0
            assert a.previous_price == 50.0
            assert a.absolute_change == -5.0
            assert a.percentage_change == -10.0
            assert a.lowest_observed == 45.0
            assert a.highest_observed == 50.0
    finally:
        await _cleanup([pid])