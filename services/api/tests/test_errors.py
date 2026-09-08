"""Unit tests for the error taxonomy."""

from __future__ import annotations

import pytest

from pricepilot.errors import (
    ErrorCode,
    PricePilotError,
    ProviderError,
    ProviderUnavailableError,
)


def test_default_status_mapping() -> None:
    assert PricePilotError(ErrorCode.NOT_FOUND, "nope").status_code == 404
    assert PricePilotError(ErrorCode.RATE_LIMITED, "slow").status_code == 429
    assert PricePilotError(ErrorCode.PROVIDER_UNAVAILABLE, "x").status_code == 503
    assert PricePilotError(ErrorCode.UPSTREAM_TIMEOUT, "x").status_code == 504


def test_provider_unavailable_carries_slot() -> None:
    err = ProviderUnavailableError("ai", "no key")
    assert err.provider == "ai"
    assert "ai" in err.message
    assert err.to_dict() == {"code": "provider_unavailable", "message": "ai: no key"}


def test_provider_error_defaults_502() -> None:
    err = ProviderError("search", "boom")
    assert err.status_code == 502
    assert err.code == ErrorCode.PROVIDER_ERROR


def test_error_is_an_exception() -> None:
    with pytest.raises(PricePilotError):
        raise ProviderError("x", "y")