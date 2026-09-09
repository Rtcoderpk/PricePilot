"""Phase 7 security regression tests.

Focuses on the concrete hardening controls added in Phase 7. Every test
corresponds to a real implemented behavior/control — no meaningless coverage.
This file grows workstream-by-workstream; each test imports only from modules
that already exist.
"""

from __future__ import annotations

import json
import logging

import pytest

# --------------------------------------------------------------------------- #
# F1 — logging actually emits structured JSON (was silently broken)
# --------------------------------------------------------------------------- #


def test_get_logger_has_json_handler():
    """Every child logger must carry the JSON formatter handler (the F1 fix)."""
    from pricepilot.logging import JsonFormatter, get_logger

    log = get_logger("sec_probe")
    assert len(log.handlers) >= 1
    assert any(isinstance(h.formatter, JsonFormatter) for h in log.handlers)


def test_logger_emits_via_handler():
    """Functional check: a logger with the JSON handler writes parseable JSON."""
    from io import StringIO

    from pricepilot.logging import JsonFormatter, get_logger

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    log = get_logger("sec_buffer")
    log.handlers.clear()
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)  # ensure the record is not filtered below level
    log.info("buffer marker %s", "data")
    lines = [ln for ln in stream.getvalue().splitlines() if ln.strip()]
    assert lines, "logger produced no output"
    payload = json.loads(lines[0])
    assert payload["message"] == "buffer marker data"
    assert payload["logger"].endswith("pricepilot.sec_buffer")


# --------------------------------------------------------------------------- #
# Observability — request ID present on every response
# --------------------------------------------------------------------------- #


def _client():
    from fastapi.testclient import TestClient

    from pricepilot.api import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def client():
    yield from _client()


def test_request_id_header_present(client):
    r = client.get("/api/v1/monitoring/status")
    assert r.status_code == 200
    assert r.headers.get("X-Request-Id")


# --------------------------------------------------------------------------- #
# F2 — chat session ownership (cross-user IDOR prevented)
# --------------------------------------------------------------------------- #

ALICE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
BOB = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def test_chat_session_bound_to_owner(client):
    """A session created by one user is not resumable by another user."""
    import asyncio

    from pricepilot.db import SessionLocal

    async def _seed():
        async with SessionLocal() as s:
            from sqlalchemy import text

            sid = "11111111-1111-4111-8111-111111111111"
            await s.execute(
                text(
                    "INSERT INTO users (id, email, created_at, updated_at) "
                    "VALUES (:id, :email, now(), now()) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": ALICE, "email": "alice@test.invalid"},
            )
            await s.execute(
                text(
                    "INSERT INTO shopping_sessions (id, user_id, run_id, applied_filters, messages, status, created_at, updated_at) "
                    "VALUES (:sid, :uid, NULL, '{}'::jsonb, '[]'::jsonb, 'active', now(), now())"
                ),
                {"sid": sid, "uid": ALICE},
            )
            await s.commit()

    async def _drop():
        async with SessionLocal() as s:
            from sqlalchemy import text

            await s.execute(
                text("DELETE FROM shopping_sessions WHERE id = :sid"),
                {"sid": "11111111-1111-4111-8111-111111111111"},
            )
            await s.execute(
                text("DELETE FROM users WHERE id = ANY(:ids)"),
                {"ids": [ALICE]},
            )
            await s.commit()

    asyncio.run(_seed())
    try:
        # Owner can resume.
        r = client.post(
            "/api/v1/shopping/chat",
            json={"query": "hello", "session_id": "11111111-1111-4111-8111-111111111111"},
            headers={"X-User-Id": ALICE},
        )
        assert r.status_code == 200

        # Another user cannot resume the same session.
        r2 = client.post(
            "/api/v1/shopping/chat",
            json={"query": "hello", "session_id": "11111111-1111-4111-8111-111111111111"},
            headers={"X-User-Id": BOB},
        )
        assert r2.status_code == 404
    finally:
        asyncio.run(_drop())


# --------------------------------------------------------------------------- #
# F3/F4 — API validation & DoS bounds
# --------------------------------------------------------------------------- #


def test_product_id_too_long_rejected(client):
    r = client.post(
        "/api/v1/tracking",
        json={"product_id": "x" * 200},
        headers={"X-User-Id": ALICE},
    )
    assert r.status_code == 422


def test_image_upload_oversize_rejected_before_processing(client):
    import io

    # Slightly over the 5 MB cap → 422, never reaching the vision provider.
    big = b"\x00" * (5 * 1024 * 1024 + 1)
    r = client.post(
        "/api/v1/shopping/image",
        files={"file": ("big.jpg", io.BytesIO(big), "image/jpeg")},
        data={"max_matches": "3"},
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# F5 — rate limiting: identity-aware keys + fail-open on Redis outage
# --------------------------------------------------------------------------- #


def test_rate_limit_key_uses_identity_when_present():
    """An X-User-Id that is a valid UUID is the rate-limit key, so limits can't
    be bypassed by rotating IPs. Also verifies invalid identities fall back to IP."""
    from pricepilot.api.v1.routes import _client_key

    class _Req:
        def __init__(self, header, host="1.2.3.4"):
            self.headers = {"x-user-id": header} if header else {}
            self.client = type("C", (), {"host": host})()

    good = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert _client_key(_Req(good)) == f"identity:{good}"
    assert _client_key(_Req("nobody")) == "1.2.3.4"  # invalid → IP fallback
    assert _client_key(_Req(None)) == "1.2.3.4"  # anonymous → IP fallback


def test_rate_limiter_fails_open_when_redis_down():
    """Rate limiting must not become a new failure point: no Redis → allow."""
    from pricepilot.rate_limit import RateLimiter

    class _BrokenRedis:
        async def incr(self, key):
            raise RuntimeError("redis down")

    limiter = RateLimiter(_BrokenRedis())
    allowed, count = _run(limiter, "key:x")
    assert allowed is True
    assert count == 0


def _run(limiter, key):
    import asyncio

    return asyncio.run(limiter.check_or_increment(key, limit=5, window_seconds=60))


# --------------------------------------------------------------------------- #
# F6 — SSRF boundary validator
# --------------------------------------------------------------------------- #


def test_ssrf_blocks_private_and_loopback():
    from pricepilot.services.url_safety import UnsafeUrlError, assert_public_https

    for url in (
        "http://localhost:8000/x",
        "http://127.0.0.1/x",
        "http://10.0.0.1/x",
        "http://192.168.1.1/x",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/x",
        "http://0.0.0.0/x",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "data:text/plain,hi",
    ):
        try:
            assert_public_https(url)
        except UnsafeUrlError:
            continue
        raise AssertionError(f"should have blocked {url}")


def test_ssrf_allows_public_https():
    from pricepilot.services.url_safety import assert_public_https

    assert_public_https("https://world.openfoodfacts.org/api/v0/product.json")
    assert_public_https("https://images.example.com/pic.png")


def test_ssrf_malformed_url_rejected():
    from pricepilot.services.url_safety import UnsafeUrlError, assert_public_https

    for url in ("", "not-a-url", "https://", "https://exa mple.com/x"):
        try:
            assert_public_https(url)
        except UnsafeUrlError:
            continue
        raise AssertionError(f"should have rejected {url!r}")


def test_production_guard_refuses_placeholder_jwt_secret():
    from pricepilot.config.settings_prod_guard import (
        assert_production_config_safe,
        placeholder_jwt_secret_allowed,
    )

    assert placeholder_jwt_secret_allowed("change-me-in-prod", app_env="test") is True
    assert placeholder_jwt_secret_allowed("change-me-in-prod", app_env="production") is False
    assert placeholder_jwt_secret_allowed("a-real-long-secret-123", app_env="production") is True
    # The lifecycle check raises in production with the placeholder.
    try:
        assert_production_config_safe(app_env="production", jwt_secret="change-me-in-prod")
    except RuntimeError:
        pass
    else:
        raise AssertionError("production guard should have refused the placeholder secret")
    # And does not raise with a strong secret in production.
    assert_production_config_safe(app_env="production", jwt_secret="a-real-long-secret-123")


def test_ssrf_public_resolution_blocks_private():
    """A hostname that resolves to a loopback/private IP must be rejected.

    Uses a deterministic localhost mapping so the test never depends on outward
    DNS. We monkeypatch getaddrinfo to avoid real network calls."""
    import socket

    from pricepilot.services.url_safety import UnsafeUrlError, assert_public_resolution

    def fake_getaddrinfo(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]

    real = socket.getaddrinfo
    socket.getaddrinfo = fake_getaddrinfo
    try:
        try:
            assert_public_resolution("evil.example.com")
        except UnsafeUrlError:
            pass
        else:
            raise AssertionError("should have blocked private resolution")
    finally:
        socket.getaddrinfo = real


# --------------------------------------------------------------------------- #
# F10 — idempotent tracking create (no TOCTOU duplicate)
# --------------------------------------------------------------------------- #


def test_tracking_create_idempotent(client):
    """Duplicate tracking create returns already_tracked (never a 500)."""
    import asyncio

    from pricepilot.db import SessionLocal

    async def _seed_product() -> str:
        async with SessionLocal() as s:
            from sqlalchemy import text

            pid = "99999999-9999-4999-8999-999999999999"
            await s.execute(
                text("INSERT INTO products (id, canonical_name, brand, is_fixture) "
                     "VALUES (:p, 'Sec Widget', 'Acme', false) ON CONFLICT (id) DO NOTHING"),
                {"p": pid},
            )
            await s.commit()
            return pid

    async def _drop(pid: str):
        async with SessionLocal() as s:
            from sqlalchemy import text

            await s.execute(text("DELETE FROM watchlists WHERE product_id = :p"), {"p": pid})
            await s.execute(text("DELETE FROM products WHERE id = :p"), {"p": pid})
            await s.execute(
                text("DELETE FROM users WHERE id = :u"),
                {"u": "cccccccc-cccc-4ccc-8ccc-cccccccccccc"},
            )
            await s.commit()

    pid = asyncio.run(_seed_product())
    user = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    try:
        r1 = client.post("/api/v1/tracking", json={"product_id": pid}, headers={"X-User-Id": user})
        assert r1.status_code in (200, 201)
        r2 = client.post("/api/v1/tracking", json={"product_id": pid}, headers={"X-User-Id": user})
        assert r2.status_code == 200
        assert r2.json().get("status") == "already_tracked"
    finally:
        asyncio.run(_drop(pid))


# --------------------------------------------------------------------------- #
# Prompt-injection-as-data — external content is never put into an LLM prompt
# --------------------------------------------------------------------------- #


def test_only_one_llm_prompt_surface_regression():
    """If a new generate_structured call site beyond intent.py appears, fail.

    Intent extraction is the ONLY LLM prompt and it only interpolates the user's
    own query. Any future agent that sends external product/seller/review text
    to a model must be reviewed explicitly — this test guards the invariant."""
    from pathlib import Path

    agents = Path(__file__).resolve().parents[1] / "pricepilot" / "agents"
    services = Path(__file__).resolve().parents[1] / "pricepilot" / "services"
    hits = []
    for root in (agents, services):
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            text = path.read_text(encoding="utf-8")
            # A call to generate_structured is the boundary where untrusted
            # content could reach a prompt; intent.py is the only expected one.
            if "generate_structured(" in text and "structured" not in path.name:
                hits.append(str(path))
    unexpected = [h for h in hits if Path(h).name != "intent.py"]
    assert not unexpected, f"unexpected LLM call sites: {unexpected}"


# --------------------------------------------------------------------------- #
# AI output safety — malformed/huge model text never trusted unsafely
# --------------------------------------------------------------------------- #


def test_ai_parser_rejects_markdown_wrapped_json():
    """Markdown-wrapped JSON must either parse cleanly to the schema or fail
    with a controlled ProviderError — never a raw crash."""
    from pricepilot.errors import ProviderError
    from pricepilot.providers.ai.openai_compatible import _parse_json_to_schema

    class _PydanticLike:
        @classmethod
        def model_validate(cls, obj):
            if not isinstance(obj, dict):
                raise ValueError("not dict")
            return {"required": 1}

    try:
        _parse_json_to_schema('```json\n{"required": 1}\n```', _PydanticLike)
    except ProviderError:
        return  # controlled failure is acceptable
    except Exception as exc:  # pragma: no cover - safety net
        raise AssertionError(f"unexpected exception type: {type(exc).__name__}") from exc


def test_ai_parser_rejects_huge_or_invalid_output():
    from pricepilot.errors import ProviderError
    from pricepilot.providers.ai.openai_compatible import _parse_json_to_schema

    class _PydanticLike:
        @classmethod
        def model_validate(cls, obj):
            if not isinstance(obj, dict):
                raise ValueError("not dict")
            return obj

    # Huge non-JSON blob → controlled ProviderError, never a raw exception.
    try:
        _parse_json_to_schema("A" * 100_000, _PydanticLike)
    except ProviderError:
        return
    except Exception as exc:  # pragma: no cover - safety net
        raise AssertionError(f"unexpected exception type: {type(exc).__name__}") from exc
    raise AssertionError("huge malformed output should not validate")  # pragma: no cover