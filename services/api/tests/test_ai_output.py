"""Tests for structured AI output handling: valid, malformed, retry, fallback,
and total-failure behavior. Never trusts raw model text."""

from __future__ import annotations

import pytest

from pricepilot.agents import structured
from pricepilot.errors import ProviderError
from pricepilot.providers.ai import AIProvider, NoopAIProvider


class _PydanticLike:
    """Minimal schema double matching the `type[BaseModel]` protocol."""

    @classmethod
    def model_validate(cls, obj):
        if not isinstance(obj, dict):
            raise ValueError("not a dict")
        if obj.get("required") is None:
            raise ValueError("missing required")
        return obj


class _GoodAI(AIProvider):
    """Returns valid structured data."""

    name = "good"

    def __init__(self):
        self.calls = 0

    async def available(self) -> bool:
        return True

    async def generate_structured(self, prompt, schema, *, max_tokens=None):
        self.calls += 1
        return schema.model_validate({"required": 1})


class _MalformedThenGood(AIProvider):
    """Returns garbage once, then valid."""

    name = "flaky"

    def __init__(self):
        self.calls = 0

    async def available(self) -> bool:
        return True

    async def generate_structured(self, prompt, schema, *, max_tokens=None):
        self.calls += 1
        if self.calls == 1:
            raise ProviderError("flaky", "LLM returned malformed JSON")
        return schema.model_validate({"required": 1})


class _AlwaysMalformed(AIProvider):
    name = "bad"

    async def available(self) -> bool:
        return True

    async def generate_structured(self, prompt, schema, *, max_tokens=None):
        raise ProviderError("bad", "LLM produced invalid output")


class _TimeoutAI(AIProvider):
    name = "slow"

    async def available(self) -> bool:
        return True

    async def generate_structured(self, prompt, schema, *, max_tokens=None):
        # simulate a hang → bounded by wait_for
        import asyncio

        await asyncio.sleep(5)
        return schema.model_validate({"required": 1})


class _UnavailableAI(AIProvider):
    name = "down"

    async def available(self) -> bool:
        return False

    async def generate_structured(self, prompt, schema, *, max_tokens=None):
        raise AssertionError("should not be called when unavailable")


async def test_valid_structured_output():
    out = await structured.generate_structured(
        "x", _PydanticLike, providers=[_GoodAI()]
    )
    assert out["required"] == 1


async def test_malformed_then_retry_succeeds():
    p = _MalformedThenGood()
    out = await structured.generate_structured("x", _PydanticLike, providers=[p])
    assert out["required"] == 1
    assert p.calls >= 2  # bounded retry happened


async def test_total_provider_failure_raises_controlled():
    with pytest.raises(structured.StructuredOutputError):
        await structured.generate_structured("x", _PydanticLike, providers=[_AlwaysMalformed()])


async def test_fallback_provider_used():
    out = await structured.generate_structured(
        "x",
        _PydanticLike,
        providers=[_AlwaysMalformed(), _GoodAI()],
    )
    assert out["required"] == 1  # fallback succeeded


async def test_no_provider_available_raises():
    with pytest.raises(structured.StructuredOutputError):
        await structured.generate_structured("x", _PydanticLike, providers=[NoopAIProvider()])


async def test_unavailable_provider_skipped():
    out = await structured.generate_structured(
        "x", _PydanticLike, providers=[_UnavailableAI(), _GoodAI()]
    )
    assert out["required"] == 1