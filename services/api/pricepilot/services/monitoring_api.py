"""Price monitoring API service — tracking CRUD, history, alerts, status.

All operations are user-scoped: the caller passes an authenticated user id and no
operation can read/modify another user's records (authorization enforced here and
later reinforced by RLS when Supabase roles are present). Never fabricates data.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.monitoring.analytics import compute_analytics

log = get_logger("services.monitoring_api")


async def create_tracking(
    session,
    *,
    user_id: str,
    product_id: str,
    target_price: float | None,
    target_currency: str | None,
    alert_preferences: dict[str, bool] | None,
) -> dict[str, Any]:
    """Track a product for this user; returns the new watchlist row or an
    existing-row notice on duplicate. Idempotent under concurrency: the unique
    (user_id, product_id) constraint plus `ON CONFLICT DO NOTHING` removes the
    SELECT→INSERT race (no more duplicate 500s)."""
    wl_id = str(uuid.uuid4())
    prefs = alert_preferences or {"price_drop": True, "new_low": True, "target_price": True}

    # The search surface returns canonical ids like `pp_gtin_<hex>` rather than a
    # `products` UUID. To make "track a search result" work end-to-end, persist a
    # products.row (+ a sku identifier) for a canonical id on first use so the
    # watchlist FK is satisfied and the monitoring worker can later match it.
    resolved_product_id = await _ensure_product_for_tracking(session, product_id)

    try:
        inserted = await session.execute(
            text(
                "INSERT INTO watchlists (id, user_id, product_id, target_price, target_currency, "
                "alert_preferences, paused, created_at, updated_at) "
                "VALUES (:id, :uid, :pid, :target, :curr, CAST(:prefs AS jsonb), false, now(), now()) "
                "ON CONFLICT (user_id, product_id) DO NOTHING RETURNING id"
            ),
            {
                "id": wl_id,
                "uid": user_id,
                "pid": resolved_product_id,
                "target": target_price,
                "curr": target_currency or "USD",
                "prefs": _json_str(prefs),
            },
        )
    except Exception:
        await session.rollback()
        log.exception("tracking: create failed for user %s product %s", user_id, product_id)
        raise

    row = inserted.mappings().first()
    if row is not None:
        await session.commit()
        return {"status": "created", "id": str(row["id"]), **prefs}

    # Conflict → the row already exists; return the existing one.
    existing = (await session.execute(
        text("SELECT id FROM watchlists WHERE user_id=:uid AND product_id=:pid"),
        {"uid": user_id, "pid": resolved_product_id},
    )).mappings().first()
    await session.rollback()  # release the aborted insert's transaction state
    if existing:
        return {"status": "already_tracked", "id": str(existing["id"])}
    return {"status": "created", "id": wl_id, **prefs}


async def _ensure_product_for_tracking(session, product_id: str) -> str:
    """Resolve a `product_id` to a real `products.id` UUID, persisting a row
    when a canonical id (e.g. `pp_gtin_<hex>` / `off_...`) is provided.

    Returns the UUID to use for the watchlist FK. Idempotent: looks up an
    existing product by its canonical id (stored as a `sku` identifier) before
    inserting.
    """
    if not product_id:
        return product_id

    # Already a UUID-shaped id → use it directly (caller is responsible for it
    # existing; the FK will reject a dangling id, which is correct).
    try:
        as_uuid = str(uuid.UUID(product_id.strip()))
        if as_uuid == product_id.strip():
            return as_uuid
    except (ValueError, AttributeError):
        pass

    canonical = product_id.strip()
    # Idempotent lookup by canonical id (stored as an `sku` identifier).
    existing = (await session.execute(
        text(
            "SELECT p.id FROM products p "
            "JOIN product_identifiers pi ON pi.product_id = p.id "
            "WHERE pi.id_type = 'sku' AND pi.id_value = :canonical "
            "LIMIT 1"
        ),
        {"canonical": canonical},
    )).mappings().first()
    if existing:
        return str(existing["id"])

    pid = str(uuid.uuid4())
    name = canonical if canonical.startswith("pp_") or canonical.startswith("off_") else canonical
    try:
        await session.execute(
            text(
                "INSERT INTO products (id, canonical_name, brand, meta, is_fixture, created_at, updated_at) "
                "VALUES (:id, :name, NULL, :meta, false, now(), now())"
            ),
            {"id": pid, "name": name[:300], "meta": json.dumps({"canonical_id": canonical})},
        )
        await session.execute(
            text(
                "INSERT INTO product_identifiers (id, product_id, id_type, id_value, source, created_at, updated_at) "
                "VALUES (:iid, :pid, 'sku', :value, 'canonical', now(), now()) "
                "ON CONFLICT (id_type, id_value) DO NOTHING"
            ),
            {"iid": str(uuid.uuid4()), "pid": pid, "value": canonical},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        log.exception("tracking: product persist failed for canonical %s", canonical)
        # Re-raise so the caller surfaces a controlled error (not a silent pass).
        raise
    return pid


async def list_tracking(session, *, user_id: str) -> list[dict[str, Any]]:
    rows = (await session.execute(
        text(
            "SELECT w.id, w.product_id, p.canonical_name AS name, w.target_price, "
            "w.target_currency, w.alert_preferences, w.paused, w.last_monitor_status, "
            "w.last_observed_at, w.created_at, w.updated_at "
            "FROM watchlists w JOIN products p ON p.id = w.product_id "
            "WHERE w.user_id = :uid ORDER BY w.created_at DESC"
        ),
        {"uid": user_id},
    )).mappings().all()
    result: list[dict[str, Any]] = []
    for r in rows:
        item = {
            "id": str(r["id"]),
            "product_id": str(r["product_id"]),
            "name": r["name"],
            "target_price": float(r["target_price"]) if r["target_price"] is not None else None,
            "target_currency": r["target_currency"],
            "alert_preferences": r["alert_preferences"] or {},
            "paused": bool(r["paused"]),
            "last_monitor_status": r["last_monitor_status"],
            "last_observed_at": r["last_observed_at"].isoformat() if r["last_observed_at"] else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        item.update(await _tracking_movement(session, str(r["product_id"])))
        result.append(item)
    return result


async def get_tracking(session, *, user_id: str, watchlist_id: str) -> dict[str, Any] | None:
    row = (await session.execute(
        text(
            "SELECT w.id, w.product_id, p.canonical_name AS name, w.target_price, "
            "w.target_currency, w.alert_preferences, w.paused, w.last_monitor_status, "
            "w.last_observed_at "
            "FROM watchlists w JOIN products p ON p.id = w.product_id "
            "WHERE w.user_id = :uid AND w.id = :wid"
        ),
        {"uid": user_id, "wid": watchlist_id},
    )).mappings().first()
    if not row:
        return None
    item = {
        "id": str(row["id"]),
        "product_id": str(row["product_id"]),
        "name": row["name"],
        "target_price": float(row["target_price"]) if row["target_price"] is not None else None,
        "target_currency": row["target_currency"],
        "alert_preferences": row["alert_preferences"] or {},
        "paused": bool(row["paused"]),
        "last_monitor_status": row["last_monitor_status"],
        "last_observed_at": row["last_observed_at"].isoformat() if row["last_observed_at"] else None,
    }
    item.update(await _tracking_movement(session, str(row["product_id"])))
    return item


async def update_tracking(
    session,
    *,
    user_id: str,
    watchlist_id: str,
    target_price: float | None,
    target_currency: str | None,
    alert_preferences: dict[str, bool] | None,
    paused: bool | None,
) -> dict[str, Any] | None:
    """Update a tracking record; returns None if it isn't the user's."""
    row = (await session.execute(
        text("SELECT id FROM watchlists WHERE user_id=:uid AND id=:wid"),
        {"uid": user_id, "wid": watchlist_id},
    )).mappings().first()
    if not row:
        return None

    sets: list[str] = ["updated_at = now()"]
    params: dict[str, Any] = {"wid": watchlist_id}
    if paused is not None:
        sets.append("paused = :paused")
        params["paused"] = paused
    if target_price is not None:
        sets.append("target_price = :target")
        params["target"] = target_price
    if target_currency:
        sets.append("target_currency = :curr")
        params["curr"] = target_currency
    if alert_preferences is not None:
        sets.append("alert_preferences = CAST(:prefs AS jsonb)")
        params["prefs"] = _json_str(alert_preferences)
    await session.execute(text(f"UPDATE watchlists SET {', '.join(sets)} WHERE id=:wid"), params)
    await session.commit()
    return await get_tracking(session, user_id=user_id, watchlist_id=watchlist_id)


async def delete_tracking(session, *, user_id: str, watchlist_id: str) -> bool:
    row = (await session.execute(
        text("SELECT id FROM watchlists WHERE user_id=:uid AND id=:wid"),
        {"uid": user_id, "wid": watchlist_id},
    )).mappings().first()
    if not row:
        return False
    await session.execute(text("DELETE FROM watchlists WHERE id=:wid"), {"wid": watchlist_id})
    await session.commit()
    return True


async def price_history(session, *, product_id: str, offer_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    """Real observation history (never synthetic) + analytics."""
    sql = "SELECT amount, currency, recorded_at, source FROM prices WHERE product_id = :pid "
    params: dict[str, Any] = {"pid": product_id}
    if offer_id:
        sql += "AND offer_id = :oid "
        params["oid"] = offer_id
    sql += "ORDER BY recorded_at ASC LIMIT :limit"
    params["limit"] = limit
    rows = (await session.execute(text(sql), params)).mappings().all()

    observations = [
        {
            "amount": float(r["amount"]),
            "currency": r["currency"],
            "observed_at": r["recorded_at"].isoformat() if r["recorded_at"] else None,
            "source": r["source"],
        }
        for r in rows
    ]
    analytics = await compute_analytics(session, product_id)
    currency = rows[-1]["currency"] if rows else None
    return {"product_id": product_id, "observations": observations, "analytics": analytics.to_dict(), "currency": currency}


async def list_alerts(session, *, user_id: str, only_unread: bool = False) -> list[dict[str, Any]]:
    """User's alert notifications (in-app) with prior/current price + event info.

    Joins notifications → price_alerts to expose event metadata.
    """
    sql = (
        "SELECT n.id AS notif_id, n.title, n.body, n.status AS notif_status, n.created_at, "
        "pa.id AS alert_id, pa.kind, pa.product_id, pa.target_amount, pa.target_currency, "
        "pa.percent_threshold, pa.triggering_offer, pa.event_key "
        "FROM notifications n LEFT JOIN price_alerts pa ON pa.id = n.alert_id "
        "WHERE n.user_id = :uid "
    )
    params: dict[str, Any] = {"uid": user_id}
    if only_unread:
        sql += "AND n.status = 'unread' "
    sql += "ORDER BY n.created_at DESC LIMIT 100"
    rows = (await session.execute(text(sql), params)).mappings().all()
    return [
        {
            "id": str(r["notif_id"]),
            "title": r["title"],
            "body": r["body"],
            "status": r["notif_status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "alert_id": str(r["alert_id"]) if r["alert_id"] else None,
            "kind": r["kind"],
            "product_id": str(r["product_id"]) if r["product_id"] else None,
            "target_amount": float(r["target_amount"]) if r["target_amount"] is not None else None,
            "percent_threshold": float(r["percent_threshold"]) if r["percent_threshold"] is not None else None,
            "triggering_offer": r["triggering_offer"] or None,
        }
        for r in rows
    ]


async def read_alert(session, *, user_id: str, notification_id: str, status: str) -> bool:
    """Mark a notification read/dismissed (only the owner's)."""
    row = (await session.execute(
        text("SELECT id FROM notifications WHERE user_id=:uid AND id=:nid"),
        {"uid": user_id, "nid": notification_id},
    )).mappings().first()
    if not row:
        return False
    await session.execute(
        text("UPDATE notifications SET status = :status WHERE id = :nid"),
        {"status": status, "nid": notification_id},
    )
    await session.commit()
    return True


async def monitoring_status(session) -> dict[str, Any]:
    """Honest monitoring capability + active tracked count."""
    enabled = settings.monitor_enabled
    provider = "available" if _provider_available() else "unavailable"
    try:
        n = (await session.execute(text("SELECT count(*) AS c FROM watchlists WHERE paused = false"))).scalar() or 0
    except Exception:
        n = 0
    message = None
    if not enabled:
        message = "Monitoring is disabled via configuration."
    elif provider != "available":
        message = "Monitoring unavailable: no real price provider is configured. Prices will not be observed."
    elif n == 0:
        message = "Monitoring is available but no products are tracked."
    return {
        "enabled": enabled,
        "provider": provider,
        "interval_seconds": settings.monitor_poll_interval_seconds,
        "tracked_products": int(n),
        "message": message,
    }


def _provider_available() -> bool:
    from pricepilot.monitoring.price_source import price_source_status

    return price_source_status() == "available"


async def _tracking_movement(session, product_id: str) -> dict[str, Any]:
    """Derive current/previous price + movement from real recorded history.

    Additive view data only — no schema change. Returns honest nulls when there
    is insufficient history rather than fabricating a movement.
    """
    if not product_id:
        return {
            "current_price": None,
            "previous_price": None,
            "percentage_change": None,
            "movement": "unknown",
            "observation_count": 0,
        }
    try:
        analytics = await compute_analytics(session, product_id)
        cur = float(analytics.current_price) if analytics.current_price is not None else None
        prev = float(analytics.previous_price) if analytics.previous_price is not None else None
        pct = float(analytics.percentage_change) if analytics.percentage_change is not None else None
        count = int(analytics.observation_count or 0)
    except Exception:
        log.exception("tracking: movement derivation failed for %s", product_id)
        cur = prev = pct = None
        count = 0

    if cur is None or prev is None or count < 2:
        movement = "unknown"
    elif abs(pct or 0) < 0.005:
        movement = "flat"
    elif (pct or 0) < 0:
        movement = "down"
    else:
        movement = "up"

    return {
        "current_price": cur,
        "previous_price": prev,
        "percentage_change": pct,
        "movement": movement,
        "observation_count": count,
    }


def _json_str(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False)