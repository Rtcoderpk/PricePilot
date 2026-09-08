"""Deterministic price analytics over STORED observations only.

Never manufactures data points. States are explicit:
  0 obs  → status="insufficient_history"
  1 obs  → current price only, status="insufficient_history" (basic)
  2+ obs → change metrics
  larger  → trend stats
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from typing import Any

from sqlalchemy import text


@dataclass
class PriceAnalytics:
    product_id: str
    status: str = "insufficient_history"  # "available" when ≥2 obs w/ change
    current_price: float | None = None
    previous_price: float | None = None
    absolute_change: float | None = None
    percentage_change: float | None = None
    lowest_observed: float | None = None
    highest_observed: float | None = None
    average_observed: float | None = None
    observation_count: int = 0
    first_observed: datetime | None = None
    last_observed: datetime | None = None
    trend: str | None = None  # "up" | "down" | "flat" | None
    currency: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "status": self.status,
            "current_price": self.current_price,
            "previous_price": self.previous_price,
            "absolute_change": self.absolute_change,
            "percentage_change": self.percentage_change,
            "lowest_observed": self.lowest_observed,
            "highest_observed": self.highest_observed,
            "average_observed": self.average_observed,
            "observation_count": self.observation_count,
            "first_observed": self.first_observed.isoformat() if self.first_observed else None,
            "last_observed": self.last_observed.isoformat() if self.last_observed else None,
            "trend": self.trend,
            "currency": self.currency,
        }


async def compute_analytics(session, product_id: str, *, limit_window_days: int | None = None) -> PriceAnalytics:
    """Compute analytics from the `prices` table for a product (oldest → newest)."""
    sql = (
        "SELECT amount, currency, recorded_at FROM prices "
        "WHERE product_id = :pid AND amount IS NOT NULL "
    )
    params: dict = {"pid": product_id}
    if limit_window_days:
        sql += "AND recorded_at >= now() - interval '1 day' * :days "
        params["days"] = limit_window_days
    sql += "ORDER BY recorded_at ASC"

    try:
        rows = (await session.execute(text(sql), params)).mappings().all()
    except Exception:
        rows = []

    amounts = [float(r["amount"]) for r in rows]
    latest = amounts[-1] if amounts else None
    currency = rows[-1]["currency"] if rows else None
    first = rows[0]["recorded_at"] if rows else None
    last = rows[-1]["recorded_at"] if rows else None

    if not amounts:
        return PriceAnalytics(product_id=product_id, status="insufficient_history", observation_count=0)

    a = PriceAnalytics(
        product_id=product_id,
        current_price=latest,
        currency=currency,
        observation_count=len(amounts),
        first_observed=first,
        last_observed=last,
    )

    if len(amounts) == 1:
        # single observation: current only, not enough for change metrics
        a.status = "insufficient_history"
        a.previous_price = None
        a.lowest_observed = a.highest_observed = a.average_observed = a.current_price
        return a

    a.lowest_observed = min(amounts)
    a.highest_observed = max(amounts)
    a.average_observed = round(statistics.mean(amounts), 2)
    a.previous_price = amounts[-2]
    a.absolute_change = round(latest - amounts[-2], 2)
    if amounts[-2]:
        a.percentage_change = round((latest - amounts[-2]) / amounts[-2] * 100.0, 2)
    a.trend = _trend(amounts)
    a.status = "available"
    return a


def _trend(amounts: list[float]) -> str | None:
    if len(amounts) < 2:
        return None
    # compare last half vs first half (simple, deterministic)
    n = len(amounts)
    first_half = statistics.mean(amounts[: n // 2])
    second_half = statistics.mean(amounts[n // 2 :])
    if second_half > first_half * 1.005:
        return "up"
    if second_half < first_half * 0.995:
        return "down"
    return "flat"