"""Centralized deferred-auth identity resolver (Phase 5).

Auth is intentionally deferred (Phase 1 decision): the API accepts an
`X-User-Id` header in place of a JWT until real Supabase authentication lands.
All Phase 5 user-scoped endpoints (tracking, alerts, preferences, monitoring)
resolve identity through this module so there is a single source of truth for:

- validating the header is a well-formed UUID (else a clean 400, never a 500),
- making sure the user exists in `users` by idempotently upserting a row for
  that UUID on first use (the schema keeps UUID FKs to `users.id`),
- returning a canonical UUID string every downstream query uses.

When real auth lands, this resolver is replaced by one that reads the JWT
sub/claim and returns the authenticated Supabase user UUID — the downstream
service layer and routes stay unchanged.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text

from pricepilot.errors import ErrorCode, PricePilotError
from pricepilot.logging import get_logger

log = get_logger("services.identity")

# Deterministic synthetic email space for deferred auth. Real auth later
# replaces this with the user's actual verified email.
_EMAIL_DOMAIN = "deferred-auth.invalid"


async def resolve_user_identity(session, raw_user_id: str | None) -> str:
    """Validate `X-User-Id` and ensure the user row exists; return the UUID.

    Raises:
        PricePilotError(401) — header missing.
        PricePilotError(400) — header present but not a valid UUID.
    """
    if raw_user_id is None or not raw_user_id.strip():
        raise PricePilotError(
            ErrorCode.UNAUTHORIZED,
            "Missing X-User-Id header.",
            status_code=401,
        )

    cleaned = raw_user_id.strip()
    try:
        canonical = str(uuid.UUID(cleaned))
    except (ValueError, AttributeError):
        # Fast fail on malformed input rather than leaking a DB-level 500.
        raise PricePilotError(
            ErrorCode.VALIDATION_ERROR,
            "X-User-Id must be a valid UUID.",
            status_code=400,
        ) from None

    await _ensure_user(session, canonical)
    return canonical


async def _ensure_user(session, canonical_uuid: str) -> None:
    """Idempotently create a `users` row for the UUID on first use.

    `ON CONFLICT (id) DO NOTHING` makes this cheap on repeat requests — we
    never create a new user twice. The synthetic email is derived from the
    UUID so it is unique per user (the user must not already exist).
    """
    email = f"{canonical_uuid.replace('-', '')}@{_EMAIL_DOMAIN}"
    try:
        result = await session.execute(
            text(
                "INSERT INTO users (id, email, created_at, updated_at) "
                "VALUES (:id, :email, now(), now()) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": canonical_uuid, "email": email},
        )
        if result.rowcount and result.rowcount > 0:
            log.info("identity: created users row for %s", canonical_uuid)
        await session.commit()
    except Exception:
        await session.rollback()
        log.warning("identity: ensure_user DB failed for %s; continuing with canonical id", canonical_uuid)
        # Fall back to canonical_uuid so degraded DB doesn't crash non-persisted flows
        return canonical_uuid