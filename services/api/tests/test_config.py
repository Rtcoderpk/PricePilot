"""Unit tests for configuration loading.

These use `monkeypatch.delenv` + `monkeypatch.setenv` because Pydantic-Settings
reads process environment with higher precedence than constructor kwargs, and
`conftest.py` sets defaults via `os.environ.setdefault`.  Environment must be
cleared per test so constructor kwargs (or no-override defaults) win.
"""

from __future__ import annotations

from pricepilot.config import Settings


def _fresh(monkeypatch, **overrides) -> Settings:
    # Clear PricePilot's real-and-default env vars so kwargs below decide.
    for key in (
        "APP_ENV",
        "LOG_LEVEL",
        "PRICEPILOT_SEARCH_PROVIDER",
        "AI_PROVIDER",
        "AI_API_KEY",
        "DATABASE_URL",
        "REDIS_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_defaults_in_test_env(monkeypatch) -> None:
    s = _fresh(monkeypatch, APP_ENV="test", LOG_LEVEL="info", PRICEPILOT_SEARCH_PROVIDER="openfoodfacts")
    assert s.app_env == "test"
    assert s.log_level == "INFO"  # coerced upper
    assert s.pricepilot_search_provider == "openfoodfacts"
    assert not s.is_production


def test_ai_provider_unset_marks_unavailable(monkeypatch) -> None:
    # Empty string (env default) is falsy → not an enabled provider.
    s = _fresh(monkeypatch, AI_PROVIDER="", AI_API_KEY="")
    assert not s.ai_provider  # "" or None both disable

    # With the search slot also unset, nothing is enabled at all.
    s2 = _fresh(monkeypatch, AI_PROVIDER="", AI_API_KEY="", PRICEPILOT_SEARCH_PROVIDER="")
    assert not s2.search_providers_enabled


def test_is_production_flag(monkeypatch) -> None:
    assert _fresh(monkeypatch, APP_ENV="production").is_production
    assert not _fresh(monkeypatch, APP_ENV="development").is_production