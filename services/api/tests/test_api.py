"""API integration tests.

Uses FastAPI TestClient with the real lifespan (Redis absent → limiter degrades).
The search provider is stubbed to an in-memory transport so tests are offline.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from pricepilot.api import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:  # runs lifespan (startup/shutdown)
        yield c


def _stub_off(client: TestClient) -> None:
    from pricepilot.providers.base import JsonClient
    from pricepilot.providers.search.openfoodfacts import OpenFoodFactsProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "products": [
                    {
                        "code": "3017620422003",
                        "product_name": "Nutella",
                        "brands": "Ferrero",
                        "url": "https://example/p/1",
                        "product_price": 4.5,
                    }
                ]
            },
            headers={"content-type": "application/json"},
        )

    inner = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://world.openfoodfacts.org",
    )
    stub = OpenFoodFactsProvider(client=JsonClient(base_url="x", timeout=1, client=inner))
    client.app.state.search_service.provider = stub


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "X-Request-Id" in resp.headers


def test_readyz_reports_clean_checks(client: TestClient) -> None:
    resp = client.get("/readyz")
    # Status depends on env (DB reachable or not); the checks object is stable.
    assert resp.status_code in {200, 503}
    body = resp.json()
    assert body["status"] in {"ready", "not_ready"}
    assert "database" in body["checks"]
    assert body["checks"]["redis"] in {"ok", "degraded"}


def test_search_success_shape(client: TestClient) -> None:
    _stub_off(client)
    resp = client.post("/api/v1/search", json={"query": "nutella"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "nutella"
    assert body["total"] == 1
    assert body["products"][0]["name"] == "Nutella"
    assert body["providers"][0]["availability"] == "available"


def test_search_validation_error(client: TestClient) -> None:
    resp = client.post("/api/v1/search", json={"query": ""})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert "details" in body["error"]


def test_search_rejects_unknown_fields(client: TestClient) -> None:
    resp = client.post("/api/v1/search", json={"query": "x", "evil": 1})
    assert resp.status_code == 422