"""Alert persistence + lifecycle (no fake alerts).

Alert records reference a tracking rule (`watchlists` row) and a product, and
carry previous/current price + change. Duplicates are prevented via a unique
`event_key` on `price_alerts`. Status: active → triggered (on persist); users can
read/dismiss notifications built from these.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003

from sqlalchemy import text

from pricepilot.logging import get_logger

log = get_logger("monitoring.alerts")


@dataclass
class AlertRecord:
    id: str
    user_id: str
    product_id: str
    alert_id: str | None  # links to price_alerts
    previous_price: float | None
    current_price: float | None
    percentage_change: float | None
    target_price: float | None
    currency: str | None
    observed_at: datetime | None
    source: str | None
    event_type: str
    status: str = "triggered"


async def persist_event_alert(
    session,
    *,
    user_id: str,
    watchlist_id: str,
    product_id: str,
    event_type: str,
    previous_price: float | None,
    current_price: float | None,
    percentage_change: float | None,
    target_price: float | None,
    currency: str | None,
    observed_at: datetime,
    source: str | None,
    event_key: str,
) -> AlertRecord | None:
    """Persist a price event as an alert, deduped by event_key.

    Returns None if the event_key already exists (duplicate prevented), or a
    populated AlertRecord.
    """
    # dedupe: does a record with this event_key already exist?
    try:
        existing = (await session.execute(
            text("SELECT id FROM price_alerts WHERE event_key = :key"),
            {"key": event_key},
        )).mappings().first()
        if existing is not None:
            return None
    except Exception:
        log.exception("alerts: dedupe lookup failed")
        return None

    alert_id = str(uuid.uuid4())
    triggering_offer = _triggering_offer_payload(event_type, current_price, previous_price, source, currency)
    pct_threshold = _pct_threshold_from_event(event_type, percentage_change)
    try:
        await session.execute(
            text(
                "INSERT INTO price_alerts (id, user_id, product_id, kind, status, "
                "target_amount, target_currency, percent_threshold, triggering_offer, "
                "event_key, created_at, updated_at) "
                "VALUES (:id, :uid, :pid, :kind, 'triggered', :target, :currency, :pct, "
                "CAST(:offer AS jsonb), :key, now(), now())"
            ),
            {
                "id": alert_id,
                "uid": user_id,
                "pid": product_id,
                "kind": _kind_for(event_type),
                "target": target_price,
                "currency": currency or "USD",
                "pct": pct_threshold,
                "offer": json.dumps(triggering_offer, ensure_ascii=False) if triggering_offer else None,
                "key": event_key,
            },
        )
    except Exception:
        log.exception("alerts: insert failed")
        return None

    # notification (in-app) referencing the alert
    try:
        title, body = _message_for(event_type, current_price, previous_price, target_price, currency)
        await session.execute(
            text(
                "INSERT INTO notifications (user_id, alert_id, channel, title, body, status, created_at) "
                "VALUES (:uid, :alert_id, 'in_app', :title, :body, 'unread', now())"
            ),
            {"uid": user_id, "alert_id": alert_id, "title": title, "body": body},
        )
    except Exception:
        log.exception("alerts: notification insert failed")

    try:
        await session.commit()
    except Exception:
        log.exception("alerts: commit failed")

    return AlertRecord(
        id=alert_id,
        user_id=user_id,
        product_id=product_id,
        alert_id=alert_id,
        previous_price=previous_price,
        current_price=current_price,
        percentage_change=percentage_change,
        target_price=target_price,
        currency=currency,
        observed_at=observed_at,
        source=source,
        event_type=event_type,
    )


def _kind_for(event_type: str) -> str:
    return {
        "new_low": "target_price",
        "target_price_reached": "target_price",
        "price_drop": "percent_drop",
        "availability_change": "back_in_stock",
    }.get(event_type, "percent_drop")


def _triggering_offer_payload(
    event_type: str,
    current_price: float | None,
    previous_price: float | None,
    source: str | None,
    currency: str | None,
) -> dict | None:
    """JSONB payload describing what triggered this alert, written to
    `triggering_offer` on `price_alerts`.  Returns None for non-price events
    (e.g. back-in-stock with no known price)."""
    if current_price is None and previous_price is None:
        return None
    return {
        "event_type": event_type,
        "current_price": current_price,
        "previous_price": previous_price,
        "source": source or "unknown",
        "currency": currency or "USD",
    }


def _pct_threshold_from_event(event_type: str, percentage_change: float | None) -> float | None:
    """Map the event's numeric percentage change to the `percent_threshold` column.
    Only relevant for percent_drop-type alerts; other events store None."""
    if event_type in ("price_drop",) and percentage_change is not None:
        return percentage_change
    return None


def _message_for(
    event_type: str,
    current: float | None,
    previous: float | None,
    target: float | None,
    currency: str | None,
) -> tuple[str, str]:
    cur = f"{current:.2f}" if current is not None else "n/a"
    prev = f"{previous:.2f}" if previous is not None else "n/a"
    if event_type == "new_low":
        return "New lowest price", f"Price hit a new low: {cur} (was {prev})"
    if event_type == "target_price_reached":
        return "Target price reached", f"Price reached your target ({target} {currency or ''}): {cur}"
    if event_type == "availability_change":
        return "Availability changed", f"Offer availability changed (current price {cur})."
    return "Price dropped", f"Price dropped from {prev} to {cur}"