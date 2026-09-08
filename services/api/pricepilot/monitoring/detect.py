"""Deterministic price-event detection over STORED observations.

Only evaluates actual observed prices. Never claims "lowest ever" unless the
stored history supports it. Returns typed events the alert pipeline can persist.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime  # noqa: TC003
from typing import Any

from sqlalchemy import text


@dataclass
class PriceEvent:
    event_type: str  # price_drop | target_price_reached | new_low | availability_change
    product_id: str
    offer_id: str
    previous_price: float | None
    current_price: float | None
    percentage_change: float | None
    target_price: float | None
    currency: str | None
    observed_at: datetime | None
    source: str | None
    event_key: str  # stable, used for dedup

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_EVENT_PRIORITY = {
    "new_low": 0,
    "target_price_reached": 1,
    "price_drop": 2,
    "availability_change": 3,
}


async def detect_events(
    session,
    *,
    product_id: str,
    offer_id: str,
    current_price: float | None,
    currency: str | None,
    target_price: float | None,
    source: str,
    observed_at: datetime,
    event_scope: str,
    prior_available: bool | None = None,
    current_available: bool | None = None,
) -> list[PriceEvent]:
    """Detect price events by comparing current vs the previous STORED observation.

    `event_scope` distinguishes the same product across offers when building the
    stable `event_key`, so we dedupe per (offer, type, scope). `prior_available`
    is the offer's availability BEFORE this poll (read before
    `record_observation` overwrites it); `current_available` is this poll's
    value. Together they enable honest back-in-stock detection.
    """
    events: list[PriceEvent] = []

    # previous real observation for this offer
    previous_price: float | None = None
    if current_price is not None:
        try:
            prev = (await session.execute(
                text(
                    "SELECT amount, recorded_at FROM prices "
                    "WHERE offer_id = :oid AND amount IS NOT NULL "
                    "AND recorded_at < :ts ORDER BY recorded_at DESC LIMIT 1"
                ),
                {"oid": offer_id, "ts": observed_at},
            )).mappings().first()
        except Exception:
            prev = None
        previous_price = float(prev["amount"]) if prev is not None and prev.get("amount") is not None else None

    # 0) availability change: back-in-stock detection.
    #    Only when prior unavailable AND current available (both have evidence)
    #    — never fabricate a transition without a prior state to compare.
    if prior_available is False and current_available is True:
        events.append(PriceEvent(
            event_type="availability_change",
            product_id=product_id,
            offer_id=offer_id,
            previous_price=previous_price,
            current_price=current_price,
            percentage_change=_pct(previous_price, current_price) if current_price is not None else None,
            target_price=target_price,
            currency=currency,
            observed_at=observed_at,
            source=source,
            event_key=f"{event_scope}:{offer_id}:back_in_stock",
        ))

    # Availability detection is independent of a price signal; remaining price
    # events need a price to compare, so return if none is observed/known.
    if current_price is None:
        events.sort(key=lambda e: _EVENT_PRIORITY.get(e.event_type, 9))
        return events

    # 1) new lowest observed — only when PRIOR history exists and current price
    #    is below the minimum of prior observations.
    try:
        low = (await session.execute(
            text(
                "SELECT MIN(amount) AS m FROM prices "
                "WHERE offer_id = :oid AND amount IS NOT NULL "
                "AND recorded_at < :ts"
            ),
            {"oid": offer_id, "ts": observed_at},
        )).mappings().first()
        prior_min = float(low["m"]) if low and low["m"] is not None else None
    except Exception:
        prior_min = None

    if previous_price is not None and prior_min is not None and current_price < prior_min:
        events.append(PriceEvent(
            event_type="new_low",
            product_id=product_id,
            offer_id=offer_id,
            previous_price=previous_price,
            current_price=current_price,
            percentage_change=_pct(previous_price, current_price),
            target_price=target_price,
            currency=currency,
            observed_at=observed_at,
            source=source,
            event_key=f"{event_scope}:{offer_id}:new_low",
        ))

    # 2) target price reached
    if target_price is not None and current_price <= target_price:
        events.append(PriceEvent(
            event_type="target_price_reached",
            product_id=product_id,
            offer_id=offer_id,
            previous_price=previous_price,
            current_price=current_price,
            percentage_change=_pct(previous_price, current_price),
            target_price=target_price,
            currency=currency,
            observed_at=observed_at,
            source=source,
            event_key=f"{event_scope}:{offer_id}:target:{target_price}",
        ))

    # 3) price drop (current below previous real observation)
    if previous_price is not None and current_price < previous_price:
        events.append(PriceEvent(
            event_type="price_drop",
            product_id=product_id,
            offer_id=offer_id,
            previous_price=previous_price,
            current_price=current_price,
            percentage_change=_pct(previous_price, current_price),
            target_price=target_price,
            currency=currency,
            observed_at=observed_at,
            source=source,
            event_key=f"{event_scope}:{offer_id}:drop",
        ))

    # sort by event priority (most important first), then keep only the top
    events.sort(key=lambda e: _EVENT_PRIORITY.get(e.event_type, 9))
    return events


def _pct(previous: float | None, current: float) -> float | None:
    if previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100.0, 2)