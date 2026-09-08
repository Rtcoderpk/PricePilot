"""Price observation persistence with duplicate prevention.

An `Observation` is a single real poll of one offer. `record_observation`
inserts into `prices` (amount/currency/recorded_at/source) only for actual
price changes within a dedupe window. Availability + shipping live on
`product_offers` and are updated separately — never manufactured.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from pricepilot.config import settings
from pricepilot.logging import get_logger

log = get_logger("monitoring.observe")


@dataclass
class Observation:
    product_id: str
    offer_id: str
    amount: float | None
    currency: str | None
    available: bool | None = None
    shipping_amount: float | None = None
    source: str = "openfoodfacts"
    observed_at: datetime | None = None


@dataclass
class ObservationResult:
    inserted: bool
    id: str | None = None
    reason: str = ""


async def record_observation(session, obs: Observation, *, window_seconds: int | None = None) -> ObservationResult:
    """Persist a real observation, skipping no-change duplicates within the window.

    Only inserts when the price differs from the last recorded observation for
    the offer. If `amount` is None, no price row is written (the offer has no
    real price) but availability is still reflected on the offer row.
    """
    window = window_seconds or settings.monitor_observation_window_seconds

    # most recent observation for this offer
    try:
        row = (await session.execute(
            text(
                "SELECT amount, recorded_at FROM prices "
                "WHERE offer_id = :oid ORDER BY recorded_at DESC LIMIT 1"
            ),
            {"oid": obs.offer_id},
        )).mappings().first()
    except Exception:
        log.exception("observe: last-row lookup failed for offer %s", obs.offer_id)
        row = None

    # duplicate check: same amount within the window → skip (idempotent monitoring)
    if row is not None:
        recent = row["recorded_at"]
        previous_amount = row["amount"]
        same_price = (previous_amount == obs.amount) if (obs.amount is not None and previous_amount is not None) else False
        if same_price and _recent_seconds(recent) < window:
            return ObservationResult(inserted=False, reason="unchanged_within_window")

    # Update offer availability/shipping every poll (it is the offer's live state).
    try:
        await session.execute(
            text(
                "UPDATE product_offers SET available = :avail, "
                "shipping_amount = COALESCE(:ship, shipping_amount), "
                "last_seen_at = now() WHERE id = :oid"
            ),
            {
                "avail": bool(obs.available) if obs.available is not None else False,
                "ship": obs.shipping_amount,
                "oid": obs.offer_id,
            },
        )
    except Exception:
        log.exception("observe: offer state update failed for %s", obs.offer_id)

    # No real price → no fabricated price row.
    if obs.amount is None:
        try:
            await session.commit()
        except Exception:
            log.exception("observe: commit failed (availability-only)")
        return ObservationResult(inserted=False, reason="no_price")

    obs_id = str(uuid.uuid4())
    try:
        await session.execute(
            text(
                "INSERT INTO prices (id, offer_id, product_id, amount, currency, source, recorded_at) "
                "VALUES (:id, :oid, :pid, :amount, :currency, :source, now())"
            ),
            {
                "id": obs_id,
                "oid": obs.offer_id,
                "pid": obs.product_id,
                "amount": obs.amount,
                "currency": obs.currency or "USD",
                "source": obs.source,
            },
        )
        await session.commit()
    except Exception:
        log.exception("observe: insert failed for offer %s", obs.offer_id)
        return ObservationResult(inserted=False, reason="insert_failed")

    return ObservationResult(inserted=True, id=obs_id, reason="inserted")


def _recent_seconds(dt: datetime) -> float:
    try:
        aware = dt if dt.tzinfo else dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return (datetime.now(aware.tzinfo) - aware).total_seconds()
    except Exception:
        return float("inf")