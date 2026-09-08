"""Monitoring orchestration: poll one offer → observe → detect → alert → notify.

The orchestrator is provider-agnostic: it receives a fetched observation and a
secretary (in-app persisted) that runs detection + alert persistence. Delivery
to external channels is optional and decoupled; a notification failure never
destroys the observation or the alert record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from pricepilot.logging import get_logger
from pricepilot.monitoring.alerts import persist_event_alert
from pricepilot.monitoring.detect import detect_events
from pricepilot.monitoring.observe import Observation, record_observation
from pricepilot.providers.notifications.registry import build_notification_provider

log = get_logger("monitoring")


async def process_service_poll(
    session,
    *,
    user_id: str | None,
    watchlist_id: str,
    product_id: str,
    offer_id: str,
    amount: float | None,
    currency: str | None,
    available: bool | None,
    source: str,
    target_price: float | None,
    event_scope: str = "wl",
) -> dict[str, Any]:
    """Process a single provider poll for a tracked watchlist entry.

    Returns a structured result (observation + events + delivery status) with
    never-fabricated values.
    """
    observed_at = datetime.now(UTC)
    result: dict[str, Any] = {"observed": False, "events": [], "delivery": None}

    # 0) capture the offer's availability BEFORE record_observation overwrites it,
    #    so detect_events can honestly compare prior → current for back-in-stock.
    prior_available = await _read_prior_available(session, offer_id)

    # 1) persist the real observation (dedupe within window)
    obs = Observation(
        product_id=product_id,
        offer_id=offer_id,
        amount=amount,
        currency=currency,
        available=available,
        source=source,
        observed_at=observed_at,
    )
    obs_result = await record_observation(session, obs)
    if obs_result.inserted:
        result["observed"] = True
    else:
        result["reason"] = obs_result.reason

    # 2) detect deterministic events from stored history. Availability
    #    transitions are evaluated even when the price observation was deduped
    #    or absent (a back-in-stock can fire without a price change).
    events = await detect_events(
        session,
        product_id=product_id,
        offer_id=offer_id,
        current_price=amount,
        currency=currency,
        target_price=target_price,
        source=source,
        observed_at=observed_at,
        event_scope=event_scope,
        prior_available=prior_available,
        current_available=available,
    )

    # 3) persist alerts (deduped by event_key)
    result["events"] = await _process_events(
        session,
        user_id=user_id,
        watchlist_id=watchlist_id,
        product_id=product_id,
        events=events,
        observed_at=observed_at,
    )

    # 4) optional external delivery — never fabricate; a failure is isolated
    if result["events"] and user_id:
        provider = build_notification_provider()
        try:
            if await provider.available():
                title = f"Price alert: {result['events'][0]['event_type']}"
                body = "A tracked product changed price. See PricePilot alerts."
                delivery = await provider.deliver(user_id=user_id, title=title, body=body)
                result["delivery"] = {"channel": delivery.channel, "status": delivery.status}
            else:
                result["delivery"] = {"channel": "in_app", "status": "unavailable"}
        except Exception:
            log.exception("notification delivery failed (does not affect alert)")
            result["delivery"] = {"channel": "fn", "status": "failed"}

    return result


async def _read_prior_available(session, offer_id: str) -> bool | None:
    """Offer availability as stored before this poll (missing → None)."""
    try:
        row = (await session.execute(
            text("SELECT available FROM product_offers WHERE id = :oid"),
            {"oid": offer_id},
        )).mappings().first()
        if row is None or row.get("available") is None:
            return None
        return bool(row["available"])
    except Exception:
        log.exception("monitoring: prior availability read failed")
        return None


async def _process_events(
    session,
    *,
    user_id: str | None,
    watchlist_id: str,
    product_id: str,
    events,
    observed_at: datetime,
) -> list[dict[str, Any]]:
    """Persist alerts for each event (deduped by event_key); never fakes a record."""
    emitted: list[dict[str, Any]] = []
    for event in events:
        if user_id is None:
            continue  # require a user context to attach an alert
        alert = await persist_event_alert(
            session,
            user_id=user_id,
            watchlist_id=watchlist_id,
            product_id=product_id,
            event_type=event.event_type,
            previous_price=event.previous_price,
            current_price=event.current_price,
            percentage_change=event.percentage_change,
            target_price=event.target_price,
            currency=event.currency,
            observed_at=observed_at,
            source=event.source,
            event_key=event.event_key,
        )
        emitted.append(
            {
                "event_type": event.event_type,
                "inserted": alert is not None,
                "previous_price": event.previous_price,
                "current_price": event.current_price,
                "percentage_change": event.percentage_change,
                "target_price": event.target_price,
            }
        )
    return emitted