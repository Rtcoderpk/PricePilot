"""User shopping preferences API service (Settings page).

Upserts a single `user_preferences` row per user (the table has a UNIQUE
constraint on user_id). All operations are user-scoped: the caller passes an
authenticated user id and no other user's preferences can be read or modified.
Never fabricates defaults — an unset row returns the honest null/defaults.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from pricepilot.logging import get_logger

log = get_logger("services.preferences")

# JSONB-typed columns need an explicit cast on write (matching monitoring_api).
_JSONB_COLUMNS = {"min_specs"}


async def get_preferences(session, *, user_id: str) -> dict[str, Any] | None:
    """Return the user's stored preferences, or None when unset (honest)."""
    row = (await session.execute(
        text(
            "SELECT preferred_brands, max_budget, min_specs, preferred_stores, "
            "preferred_condition, price_vs_quality, currency_code, shopping_locale, "
            "updated_at "
            "FROM user_preferences WHERE user_id = :uid"
        ),
        {"uid": user_id},
    )).mappings().first()
    if not row:
        return None
    return {
        "preferred_brands": list(row["preferred_brands"] or []),
        "max_budget": float(row["max_budget"]) if row["max_budget"] is not None else None,
        "min_specs": row["min_specs"] or {},
        "preferred_stores": list(row["preferred_stores"] or []),
        "preferred_condition": list(row["preferred_condition"] or []),
        "price_vs_quality": float(row["price_vs_quality"]) if row["price_vs_quality"] is not None else None,
        "currency_code": row["currency_code"],
        "shopping_locale": row["shopping_locale"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


async def upsert_preferences(session, *, user_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Create or update the user's preference row from a partial field dict."""
    if not fields:
        # ensure a row exists so the Settings page has a stable identity
        await _ensure_row(session, user_id=user_id)
        await session.commit()
        return await get_preferences(session, user_id=user_id) or {}

    sets = ["updated_at = now()"]
    params: dict[str, Any] = {"uid": user_id}
    for key, value in fields.items():
        column = _COLUMN_FOR_UPDATE.get(key)
        if column is None:
            continue
        # "0 to clear" convention for max_budget, matching TrackUpdate
        if key == "max_budget" and value == 0:
            value = None
        if column in _JSONB_COLUMNS and value is not None:
            sets.append(f"{column} = CAST(:{key} AS jsonb)")
        else:
            sets.append(f"{column} = :{key}")
        params[key] = _param_value(column, value)

    await _ensure_row(session, user_id=user_id)
    await session.execute(
        text(f"UPDATE user_preferences SET {', '.join(sets)} WHERE user_id = :uid"),
        params,
    )
    await session.commit()
    return await get_preferences(session, user_id=user_id) or {}


async def _ensure_row(session, *, user_id: str) -> None:
    """Create the user's preference row on first write (idempotent)."""
    await session.execute(
        text(
            "INSERT INTO user_preferences (user_id, updated_at) "
            "VALUES (:uid, now()) "
            "ON CONFLICT (user_id) DO UPDATE SET updated_at = user_preferences.updated_at"
        ),
        {"uid": user_id},
    )


def _param_value(column: str, value: Any):
    if value is None:
        return None
    if column in _JSONB_COLUMNS:
        return json.dumps(value, ensure_ascii=False)
    return value


_COLUMN_FOR_UPDATE: dict[str, str] = {
    "preferred_brands": "preferred_brands",
    "max_budget": "max_budget",
    "min_specs": "min_specs",
    "preferred_stores": "preferred_stores",
    "preferred_condition": "preferred_condition",
    "price_vs_quality": "price_vs_quality",
    "currency_code": "currency_code",
    "shopping_locale": "shopping_locale",
}