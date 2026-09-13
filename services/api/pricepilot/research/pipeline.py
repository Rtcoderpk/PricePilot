"""Research pipeline orchestrator — one image/voice/text request end-to-end.

Stages (each logged with request_id + duration):
  INPUT → UNDERSTANDING → SEARCH → VERIFICATION → COMPARISON → RECOMMENDATION → RESPONSE

Only Gemini vision/understanding is used where required; retrieval is real and
deterministic. Results are cached in Redis (when available) keyed by the
canonical search queries, and provider failures degrade gracefully.
"""

from __future__ import annotations

import time

from pricepilot.logging import get_logger
from pricepilot.models import ProductQuery, SupplierResult

log = get_logger("research.pipeline")

_STAGE_ORDER = ["INPUT", "UNDERSTANDING", "SEARCH", "VERIFICATION", "COMPARISON", "RECOMMENDATION", "RESPONSE"]


def _stage(stage: str, request_id: str, started: float, details: str = "") -> None:
    log.info(
        "request=%s stage=%s duration_ms=%d details=%s",
        request_id, stage, int((time.monotonic() - started) * 1000), details,
    )


async def run_text_research(
    *,
    request_id: str,
    text: str,
    user_id: str | None,
    use_gemini: bool,
    cache=None,
) -> dict:
    started = time.monotonic()
    _stage("INPUT", request_id, started, "text")

    from pricepilot.research.input_router import route_text
    from pricepilot.research.response_agent import build_response
    from pricepilot.research.search_agent import search_suppliers

    query = route_text(text, use_gemini=use_gemini)
    _stage("UNDERSTANDING", request_id, started, f"queries={len(query.search_queries)}")

    # Cache the search phase by canonical query (Redis, when present).
    cache_key = None
    if cache is not None and query.search_queries:
        cache_key = "research:" + ":".join(query.search_queries)[:200]
        cached = await _get_cached(cache, cache_key)
        if cached is not None:
            _stage("SEARCH", request_id, started, "cache-hit")
            _stage("VERIFICATION", request_id, started, "cache-hit")
            _stage("COMPARISON", request_id, started, "cache-hit")
            _stage("RECOMMENDATION", request_id, started, "cache-hit")
            _stage("RESPONSE", request_id, started, "cache-hit")
            return compressed(list(cached), query, request_id)

    results: list[SupplierResult] = []
    for q in query.search_queries:
        found = await search_suppliers(q, max_results=8)
        results.extend(found)
        if len(results) >= 12:
            break
    _stage("SEARCH", request_id, started, f"results={len(results)}")

    # Jina Page Reader enrichment for candidate URLs (Section 12)
    from pricepilot.services.jina_reader import read_live_page
    for r in results[:3]:
        if r.url:
            try:
                page_info = await read_live_page(r.url, timeout=5.0)
                if page_info.get("status") == "success":
                    if page_info.get("price") is not None:
                        r.price = page_info["price"]
                        r.currency = page_info.get("currency") or r.currency
                    if page_info.get("stock"):
                        r.availability = page_info["stock"]
            except Exception:
                pass

    if cache is not None and cache_key and results:
        await _set_cached(cache, cache_key, results)

    response = build_response(results, query=query, quantity=query.quantity)
    response["request_id"] = request_id
    response["user_id"] = user_id
    response["stages"] = _STAGE_ORDER
    await persist_run(
        user_id=user_id, input_type="text", original_request=text,
        query=query, response=response,
    )
    _stage("RESPONSE", request_id, started, "done")
    return response


async def run_image_research(
    *,
    request_id: str,
    image_bytes: bytes,
    mime_type: str,
    user_id: str | None,
    cache=None,
) -> dict:
    started = time.monotonic()
    _stage("INPUT", request_id, started, "image")

    from pricepilot.research.image import extract_product_from_image
    from pricepilot.research.input_router import extraction_to_query
    from pricepilot.research.response_agent import build_response
    from pricepilot.research.search_agent import search_suppliers

    extraction, notice = await extract_product_from_image(image_bytes, mime_type, vision_required=True)
    _stage("UNDERSTANDING", request_id, started, f"confidence={extraction.confidence} notice={notice}")

    query: ProductQuery = extraction_to_query(extraction)
    if extraction.confidence == 0.0:
        # Vision not available/config failed → return an honest "not processed" envelope.
        return {
            "request_id": request_id,
            "user_id": user_id,
            "stages": _STAGE_ORDER,
            "product_understanding": None,
            "suppliers": [],
            "verifications": [],
            "comparison": [],
            "recommendation": None,
            "currency_conflict": False,
            "notice": notice,
            "response_text": "Unable to identify the product in the image.",
        }

    results: list[SupplierResult] = []
    for q in query.search_queries:
        found = await search_suppliers(q, max_results=8)
        results.extend(found)
        if len(results) >= 12:
            break
    _stage("SEARCH", request_id, started, f"results={len(results)}")

    response = build_response(results, query=query, quantity=query.quantity)
    response.update(
        {
            "request_id": request_id,
            "user_id": user_id,
            "stages": _STAGE_ORDER,
            "notice": notice,
            "extraction": extraction.model_dump(mode="json"),
        }
    )
    return response


def compressed(suppliers: list, query, request_id: str) -> dict:
    from pricepilot.research.response_agent import build_response

    response = build_response(suppliers, query=query, quantity=query.quantity)
    response["request_id"] = request_id
    response["stages"] = _STAGE_ORDER
    response["cached"] = True
    return response


async def persist_run(
    *,
    user_id: str | None,
    input_type: str,
    original_request: str | None,
    query: ProductQuery | None,
    response: dict,
) -> None:
    """Persist a research run (only when a user identity is present)."""
    import json
    import uuid

    from sqlalchemy import text

    from pricepilot.db import SessionLocal

    if not user_id:
        return
    try:
        async with SessionLocal() as session:
            await session.execute(
                text(
                    "INSERT INTO research_runs "
                    "(id, user_id, input_type, original_request, product_query, results, recommendation, status, request_id, created_at) "
                    "VALUES (:id, :uid, :itype, :oreq, CAST(:pq AS jsonb), CAST(:res AS jsonb), CAST(:rec AS jsonb), 'completed', :rid, now())"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "uid": user_id,
                    "itype": input_type,
                    "oreq": original_request,
                    "pq": json.dumps(query.model_dump(mode="json")) if query else None,
                    "res": json.dumps(response.get("suppliers", [])),
                    "rec": json.dumps(
                        {"recommendation": response.get("recommendation"), "comparison": response.get("comparison")}
                    ),
                    "rid": response.get("request_id"),
                },
            )
            await session.commit()
    except Exception:
        log.warning("research persist failed for user %s", user_id, exc_info=True)


async def _get_cached(cache, key: str) -> list | None:
    try:
        raw = await cache.get(key)
        if raw is None:
            return None
        return [SupplierResult.model_validate(d) for d in raw] if isinstance(raw, list) else None
    except Exception:
        log.warning("research cache read failed for %s", key)
        return None


async def _set_cached(cache, key: str, results: list[SupplierResult]) -> None:
    try:
        await cache.set(key, [r.model_dump(mode="json") for r in results], ex=300)
    except Exception:
        log.warning("research cache write failed for %s", key)