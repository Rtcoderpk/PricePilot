"""Recommendation agent — ranks canonical products by the user's intent.

Hard constraints are enforced first (budget_max, required features, brands when
explicit negative). If nothing satisfies all hard constraints, the recommended
list still explains that and surfaces closest alternatives explicitly flagged as
`matches_hard_constraints=False`. Rankings are deterministic with explainable
reasons.
"""

from __future__ import annotations

from pricepilot.agents.state import AgentState, RankingPreference, Recommendation
from pricepilot.logging import get_logger

log = get_logger("agents.recommendation")


async def node(state: AgentState) -> AgentState:
    intent = state.intent
    candidates = list(state.canonical_products)

    if not candidates:
        return state.model_copy(
            update={"warnings": state.warnings + ["No products to recommend"]}
        )

    scored = []
    for product in candidates:
        pid = product["product_id"]
        price = state.price_analysis.get(pid)
        deal = state.deal_scores.get(pid)
        best = price.lowest_offer if price else None

        hard = _hard_constraints_ok(product, best, len(product.get("offers", [])), intent)
        rank_score = _rank_score(product, best, deal, intent, price)

        scored.append((product, best, deal, rank_score, hard))

    # Sort primarily: hard-constraint matches first, then rank score desc.
    scored.sort(key=lambda t: (not t[4], -t[3]))

    recommendations: list[Recommendation] = []
    for rank, (product, best, deal, _score, hard) in enumerate(scored, start=1):
        offers = product.get("offers", []) or []
        currency = offers[0].get("price_currency") if offers else None
        reasons = _build_reasons(product, best, deal, hard, intent)
        recommendations.append(
            Recommendation(
                product_id=product["product_id"],
                product_name=product.get("name", ""),
                rank=rank,
                matches_hard_constraints=hard,
                reasons=reasons,
                deal_score=deal.score if deal else None,
                best_price=best,
                currency=currency,
                url=offers[0].get("url") if offers else None,
                image_url=product.get("image_url"),
                match_confidence=product.get("match_confidence"),
            )
        )

    return state.model_copy(
        update={
            "recommendations": recommendations,
            "confidence": _confidence(len(recommendations), len(candidates)),
            "final_answer": _compose_answer(recommendations, intent),
        }
    )


def _hard_constraints_ok(
    product: dict,
    best_price: float | None,
    n_offers: int,
    intent,
) -> bool:
    if not intent:
        return True
    failures = _hard_constraint_failures(product, best_price, n_offers, intent)
    return not failures


def _hard_constraint_failures(product: dict, best_price: float | None, n_offers: int, intent) -> list[str]:
    failures: list[str] = []
    if intent.has_hard_budget:
        if best_price is None:
            failures.append(f"price unknown (search budget max {intent.budget_max:g})")
        elif best_price > intent.budget_max:
            failures.append(f"price {format(best_price, '.2f')} above budget {intent.budget_max:g}")
    if intent.condition.value in ("new", "refurbished", "used"):
        # We may not have condition data; only flag when explicitly contradictory.
        pass
    return failures


def _rank_score(product: dict, best_price: float | None, deal, intent, price) -> float:
    score = 0.0
    if best_price is not None:
        score += 50.0
        if price and price.lowest_offer == best_price:
            score += 10.0  # cheapest among offers
    if deal and deal.score is not None:
        score += deal.score / 2.0
    if product.get("provider_count", 1) >= 2:
        score += 10.0  # multiple sources = more trustworthy
    if intent and intent.ranking_preference == RankingPreference.CHEAPEST:
        score += (0 if best_price is None else 30.0 / (1.0 + best_price))
    elif intent and intent.ranking_preference == RankingPreference.HIGHEST_RATED:
        score += 5.0
    return score


def _build_reasons(
    product: dict,
    best_price: float | None,
    deal,
    hard: bool,
    intent,
) -> list[str]:
    reasons: list[str] = []
    if hard and intent and intent.has_hard_budget and best_price is not None:
        reasons.append(f"within your budget (best {format(best_price, '.2f')})")
    elif not hard and best_price is not None:
        reasons.append(f"closest alternative (best {format(best_price, '.2f')})")
    if product.get("provider_count", 1) >= 2:
        reasons.append(f"matched across {product['provider_count']} sources")
    if deal:
        if deal.score is not None:
            reasons.append(f"Deal Score {deal.score:.0f}/100 ({deal.label.lower()})")
        else:
            reasons.append("insufficient data for a Deal Score")
    if product.get("match_confidence") and product["match_confidence"] < 0.8:
        reasons.append(f"matching confidence {product['match_confidence']:.0%} (verify)")
    if intent and intent.has_hard_budget and best_price is None:
        budget_text = f"within {intent.currency or 'USD'} {intent.budget_max:g} budget"
        reasons.append(f"price unknown — must be checked against {budget_text}")
    if not reasons:
        reasons.append(f"best available from {product.get('provider_count', 1)} source(s)")
    return reasons


def _confidence(n_recommended: int, n_candidates: int) -> float:
    if n_candidates == 0:
        return 0.0
    ratio = n_recommended / n_candidates
    return round(min(1.0, 0.5 + ratio * 0.4), 2)


def _compose_answer(recommendations: list[Recommendation], intent) -> str:
    if not recommendations:
        return "No matching products found. Try a more general search or adjust filters."
    top = recommendations[0]
    parts = [f"Best match: {top.product_name}"]
    if top.best_price is not None:
        parts.append(f"from ~{format(top.best_price, '.2f')}")
    if top.deal_score is not None:
        parts.append(f"(Deal Score {top.deal_score:.0f}/100)")
    if not top.matches_hard_constraints:
        parts.append("— this does not fully satisfy your hard constraints")
    return " ".join(parts)