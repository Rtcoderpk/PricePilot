"""Phase 5 identity resolver unit tests (validation branches, no DB).

The define / canonicalize branches are covered here; the idempotent `users`
upsert requires the live DB and is covered by test_phase5_api.py. All paths hit
the real error taxonomy so malformed identity can never leak a 500.
"""

from __future__ import annotations

import pytest

from pricepilot.errors import ErrorCode, PricePilotError
from pricepilot.services.identity import _ensure_user, resolve_user_identity

GOOD = "11111111-1111-4111-8111-111111111111"


class _FakeSession:
    """Records the last INSERT into `users` and behaves idempotently."""

    def __init__(self) -> None:
        self.executed: list[tuple] = []
        self.rowcount = 0
        self.committed = 0
        self.rolled_back = 0

    async def execute(self, stmt, params):
        self.executed.append((str(stmt), params))
        return self

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1


async def test_missing_header_raises_unauthorized():
    with pytest.raises(PricePilotError) as ei:
        await resolve_user_identity(_FakeSession(), None)
    assert ei.value.status_code == 401
    assert ei.value.code == ErrorCode.UNAUTHORIZED


async def test_blank_header_raises_unauthorized():
    with pytest.raises(PricePilotError) as ei:
        await resolve_user_identity(_FakeSession(), "   ")
    assert ei.value.status_code == 401


async def test_invalid_uuid_raises_validation_400():
    with pytest.raises(PricePilotError) as ei:
        await resolve_user_identity(_FakeSession(), "nobody")
    assert ei.value.status_code == 400
    assert ei.value.code == ErrorCode.VALIDATION_ERROR


async def test_non_string_null_bytes_invalid():
    with pytest.raises(PricePilotError) as ei:
        await resolve_user_identity(_FakeSession(), "")
    assert ei.value.status_code == 401


async def test_valid_uuid_canonicalizes_and_records_insert():
    s = _FakeSession()
    canonical = await resolve_user_identity(s, GOOD)
    assert canonical == GOOD
    assert s.committed == 1
    assert len(s.executed) == 1
    sql, params = s.executed[0]
    assert "INSERT INTO users" in sql
    assert params["id"] == GOOD
    assert params["email"].endswith("@deferred-auth.invalid")


async def test_valid_uuid_with_braces_canonicalizes():
    s = _FakeSession()
    mixed = "11111111-1111-4111-8111-111111111111"
    canonical = await resolve_user_identity(s, mixed)
    assert canonical == mixed


async def test_ensure_user_commits():
    s = _FakeSession()
    await _ensure_user(s, GOOD)
    assert s.committed == 1