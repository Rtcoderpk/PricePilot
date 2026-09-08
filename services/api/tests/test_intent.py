"""Intent extraction tests (deterministic parser + LLM mapping)."""

from __future__ import annotations

from pricepilot.agents.intent import _parse_deterministic, extract_intent


def test_budget_extraction():
    intent = _parse_deterministic("laptop under $700")
    assert intent.budget_max == 700.0
    assert intent.currency == "USD"


def test_budget_min_and_range():
    intent = _parse_deterministic("phone between 500 and 800 rupees")
    assert intent.budget_min == 500.0
    assert intent.budget_max == 800.0
    assert intent.currency == "INR"


def test_hard_constraints():
    intent = _parse_deterministic("Samsung TV under 700 with low input lag")
    assert intent.budget_max == 700.0
    assert "samsung" in intent.brands
    assert intent.has_hard_budget


def test_ambiguous_query_does_not_invent():
    intent = _parse_deterministic("show me something nice")
    assert intent.budget_max is None
    assert intent.budget_min is None
    assert intent.brands == []
    assert intent.category is None


def test_condition_used():
    intent = _parse_deterministic("refurbished phone")
    assert intent.condition.value == "refurbished"


def test_urgency():
    intent = _parse_deterministic("need it soon")
    assert intent.urgency.value == "soon"


def test_extract_intent_no_llm_fallback():
    # With use_llm False (or AI unavailable) we get a valid typed intent.
    intent = _parse_deterministic("gaming laptop under 1000")
    assert intent.budget_max == 1000.0
    assert intent.use_case == "gaming"


async def test_extract_intent_degraded_when_no_ai():
    # No AI provider configured → deterministic fallback never crashes.
    intent = await extract_intent("OLED TV over 900 dollars", use_llm=True)
    assert intent.raw_query == "OLED TV over 900 dollars"
    assert intent.budget_min == 900.0
    assert intent.currency in ("USD", None)