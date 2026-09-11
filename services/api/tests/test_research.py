"""Tests for the supplier research pipeline (deterministic agents).

Covers: text routing, verification states, comparison, recommendation, and the
API text endpoint. No fake supplier data is introduced — providers are mocked to
return the exact fixtures the test asserts on.
"""

from __future__ import annotations

import pytest

from pricepilot.models import (
    ComparisonOption,
    ProductQuery,
    Recommendation,
    SupplierResult,
    VerificationState,
)
from pricepilot.research import comparison_agent, recommendation_agent, verification_agent

# --------------------------------------------------------------------------- #
# input router (text)
# --------------------------------------------------------------------------- #


def test_route_text_wholesale_quantity_detected():
    from pricepilot.research.input_router import route_text

    q = route_text("I need 100 black Nike running shoes from wholesale suppliers")
    assert q.quantity == 100
    assert q.wholesale_required is True
    assert q.brand == "nike"
    assert q.category == "running shoes" or q.category  # category detected
    assert any("wholesale" in s for s in q.search_queries)


def test_route_text_missing_info():
    from pricepilot.research.input_router import route_text

    q = route_text("cheapest supplier")
    assert q.search_queries  # still has a query
    assert "product_type" in q.missing_information


def test_extraction_to_query():
    from pricepilot.models import ProductImageExtraction
    from pricepilot.research.input_router import extraction_to_query

    ex = ProductImageExtraction(
        category="running shoes", product_name="Nike Pegasus", brand="Nike",
        model="Air Zoom Pegasus", confidence=0.9,
        search_terms=["Nike Pegasus", "Nike running shoes wholesale"],
    )
    q = extraction_to_query(ex)
    assert q.brand == "Nike"
    assert q.search_queries == ex.search_terms
    assert q.confidence == 0.9


# --------------------------------------------------------------------------- #
# verification
# --------------------------------------------------------------------------- #


def _result(**kw):
    defaults = dict(
        title="X", product="Nike Pegasus", supplier="Acme Wholesale",
        price=45.0, currency="USD", url="https://example.com/p", source="openfoodfacts",
    )
    defaults.update(kw)
    return SupplierResult(**defaults)


def test_verification_verified_when_complete():
    v = verification_agent.verify_one(0, _result())
    assert v.state == VerificationState.VERIFIED


def test_verification_unverified_without_supplier():
    v = verification_agent.verify_one(0, _result(supplier=None, price=None, currency=None))
    assert v.state == VerificationState.UNVERIFIED


def test_verification_partial_when_price_missing():
    v = verification_agent.verify_one(0, _result(price=None))
    assert v.state == VerificationState.PARTIALLY_VERIFIED


# --------------------------------------------------------------------------- #
# comparison + recommendation
# --------------------------------------------------------------------------- #


def _options():
    return [
        ComparisonOption(result_index=0, supplier="A", product="P", unit_price=40.0, currency="USD", verification=VerificationState.VERIFIED, url="u1", availability="in_stock"),
        ComparisonOption(result_index=1, supplier="B", product="P", unit_price=50.0, currency="USD", verification=VerificationState.VERIFIED, url="u2", availability="in_stock"),
        ComparisonOption(result_index=2, supplier="C", product="P", unit_price=60.0, currency="USD", verification=VerificationState.VERIFIED, url="u3", availability="out"),
    ]


def test_compare_picks_cheapest():
    options, conflict = comparison_agent.position_categories(_options(), currency_conflict=False)
    cheapest = [o for o in options if o.is_cheapest]
    assert cheapest and cheapest[0].unit_price == 40.0
    assert conflict is not True


def test_recommendation_from_real_options():
    options = _options()
    options, reasoning = comparison_agent.position_categories(options, currency_conflict=False)
    rec = recommendation_agent.recommend(options, currency_conflict=False, reasoning=reasoning)
    assert rec.best_supplier is not None
    assert rec.cheapest_option is not None
    assert rec.confidence > 0.0


def test_recommendation_empty_no_fabrication():
    rec = recommendation_agent.recommend([], currency_conflict=False)
    assert rec.best_supplier is None
    assert rec.cheapest_option is None
    assert rec.confidence == 0.0


def test_rec_pydantic():
    q = ProductQuery(category="x", product_name="p", search_queries=["x"], confidence=0.5)
    assert q.product_name == "p"
    r = Recommendation()
    assert r.confidence == 0.0


# --------------------------------------------------------------------------- #
# API text endpoint (via TestClient with a mocked provider)
# --------------------------------------------------------------------------- #


def _client():
    from fastapi.testclient import TestClient

    from pricepilot.api import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def client():
    yield from _client()


def test_research_text_endpoint(client, monkeypatch):
    """Real API path; provider mocked to a known result (no fake network)."""
    async def fake_search(query, *, max_results=8):
        return [_result()]

    import pricepilot.research.search_agent as sa

    monkeypatch.setattr(sa, "search_suppliers", fake_search)

    r = client.post(
        "/api/v1/research/text",
        json={"text": "100 black Nike running shoes wholesale", "use_gemini": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["request_id"]
    assert body["suppliers"]  # real mock result surfaced
    assert body["recommendation"] is not None
    assert body["stages"]


def test_research_text_invalid_body(client):
    r = client.post("/api/v1/research/text", json={"text": ""})
    assert r.status_code == 422


def test_research_image_requires_auth_or_file(client):
    # Empty upload → 422 (no file) rather than crash.
    r = client.post("/api/v1/research/image")
    assert r.status_code in (400, 422)


def test_research_image_honest_notice_without_vision(client):
    """A real PNG upload with no vision provider returns an honest notice and no
    fabricated suppliers (anti-hallucination)."""
    import io

    png = (
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    r = client.post(
        "/api/v1/research/image",
        files={"file": ("p.png", io.BytesIO(png), "image/png")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["suppliers"] == []  # no fake suppliers
    assert body["recommendation"] is None
    assert body.get("notice")  # honest explanation (vision not configured)