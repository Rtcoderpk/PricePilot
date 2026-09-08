"""Review Intelligence agent — themes from REAL review rows only.

Reads `reviews` from the database for each canonical product (matched via the
product GTIN/identifier when available), runs deterministic theme extraction,
and writes a `review_summaries` row. When there are zero real review rows it
returns `review_data_unavailable` — no fabricated reviews or quotes.

Also consults a configured `ReviewProvider` (if any) via registry.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text

from pricepilot.agents.state import AgentState, ReviewAnalysis, SourceRef
from pricepilot.logging import get_logger
from pricepilot.providers.reviews import NoopReviewProvider
from pricepilot.providers.reviews.registry import build_review_provider
from pricepilot.services.review_themes import extract_themes

log = get_logger("agents.review")


def _product_identifiers(product: dict) -> list[str]:
    """Collect strong identifiers (gtin/ean/... values) from product offers."""
    ids: set[str] = set()
    for offer in product.get("offers", []) or []:
        for ident in offer.get("identifiers", []) or []:
            if ident.get("type") in ("gtin", "ean", "upc", "mpn") and ident.get("value"):
                ids.add(str(ident["value"]))
        if offer.get("raw", {}).get("code"):
            ids.add(str(offer["raw"]["code"]))
    return list(ids)


async def _fetch_reviews(
    session,
    identifiers: list[str],
    *,
    limit: int = 50,
) -> list[dict]:
    """Query the `reviews` table for rows matching the product's identifiers."""
    if not identifiers:
        return []
    rows: list[dict] = []
    try:
        result = await session.execute(
            text(
                "SELECT r.title, r.body, r.rating, r.review_date, r.source "
                "FROM reviews r "
                "JOIN product_identifiers pi ON pi.product_id = r.product_id "
                "WHERE pi.id_type IN ('gtin','ean','upc','mpn') "
                "AND pi.id_value = ANY(:ids) "
                "ORDER BY r.review_date DESC NULLS LAST "
                "LIMIT :limit"
            ),
            {"ids": identifiers, "limit": limit},
        )
        rows = [dict(row._mapping) for row in result]
    except Exception:
        # DB issues must not crash the node; carry on with whatever we have.
        log.exception("review query failed")
    return rows


async def node(state: AgentState, *, session=None) -> AgentState:
    # Honest no-op path when no DB session is provided (e.g. unit tests).
    if session is None:
        return _honest_unavailable(state)

    provider = build_review_provider()
    analysis = dict(state.review_analysis)

    for product in state.canonical_products:
        pid = product["product_id"]
        ids = _product_identifiers(product)
        rows = await _fetch_reviews(session, ids)

        # If a review provider is configured AND returns records, combine with
        # DB rows; dedupe is by source (best-effort here).
        provider_rows: list[dict] = []
        if not isinstance(provider, NoopReviewProvider):
            try:
                fetched = await provider.fetch(pid, limit=25)
                provider_rows = [
                    {
                        "title": r.title,
                        "body": r.body,
                        "rating": r.rating,
                        "review_date": r.review_date,
                        "source": r.source,
                    }
                    for r in fetched
                ]
            except Exception:
                log.exception("review provider fetch failed for %s", pid)

        combined = rows + provider_rows
        if not combined:
            analysis[pid] = ReviewAnalysis(product_id=pid, status="review_data_unavailable")
            continue

        bodies = [r.get("body") or "" for r in combined]
        ratings = [r.get("rating") for r in combined]
        themes = extract_themes(bodies, ratings=ratings)

        n = len(combined)
        if n >= 30:
            confidence = "high"
        elif n >= 8:
            confidence = "medium"
        else:
            confidence = "low"

        try:
            await session.execute(
                text(
                    "INSERT INTO review_summaries (product_id, positives, negatives, "
                    "common_complaints, common_strengths, generated_at, source_data, created_at, updated_at) "
                    "VALUES (:pid, :pos, :neg, :complaints, :strengths, now(), :source, now(), now()) "
                    "ON CONFLICT (product_id) DO UPDATE SET "
                    "positives=EXCLUDED.positives, negatives=EXCLUDED.negatives, "
                    "common_complaints=EXCLUDED.common_complaints, common_strengths=EXCLUDED.common_strengths, "
                    "generated_at=EXCLUDED.generated_at, updated_at=now()"
                ),
                {
                    "pid": pid,
                    "pos": themes.positives,
                    "neg": themes.negatives,
                    "complaints": themes.common_complaints,
                    "strengths": themes.common_strengths,
                    "source": {"count": n, "providers": sorted({r.get("source") for r in combined if r.get("source")})},
                },
            )
            await session.commit()
        except Exception:
            log.exception("review_summaries upsert failed for %s", pid)

        analysis[pid] = ReviewAnalysis(
            product_id=pid,
            status="available",
            positive_themes=themes.positives,
            negative_themes=themes.negatives,
            common_complaints=themes.common_complaints,
            common_strengths=themes.common_strengths,
            sentiment_summary=themes.sentiment_summary,
            review_count=n,
            review_freshness=_freshness(combined),
            confidence=confidence,
            source_refs=[
                SourceRef(source=r.get("source") or "reviews", url=None, timestamp=datetime.now(UTC))
                for r in combined[:5]
            ],
        )
    return state.model_copy(update={"review_analysis": analysis})


def _honest_unavailable(state: AgentState) -> AgentState:
    analysis = dict(state.review_analysis)
    for product in state.canonical_products:
        analysis[product["product_id"]] = ReviewAnalysis(
            product_id=product["product_id"], status="review_data_unavailable"
        )
    return state.model_copy(update={"review_analysis": analysis})


def _freshness(rows: list[dict]) -> str:
    dates = [r.get("review_date") for r in rows if r.get("review_date")]
    if not dates:
        return "unknown"
    newest = max(dates)
    try:
        aware = newest if newest.tzinfo else newest.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - aware).days
    except TypeError:
        age_days = 999
    if age_days <= 30:
        return "recent"
    if age_days <= 180:
        return "6 months"
    return "over 6 months"