"""Should I Buy? agent — explainable BUY / WAIT / AVOID from real signals.

Rules are deterministic over the deal score, seller confidence, and price
position computed by earlier nodes:
  BUY    → real price present AND deal ≥ 65 AND seller is verified/limited
  WAIT   → real price present but deal < 65 OR seller insufficient (no urgent reason)
  AVOID  → all core signals missing/misleading (no price, seller insufficient,
            no review) — suggests caution
  INSUFFICIENT_DATA → no price AND no deal score (cannot judge)

Never invents a reason or a signal. Every verdict carries its real reasons.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pricepilot.agents.state import (
    AgentState,
    SellerSignalLabel,
    ShouldIBuy,
    SibtVerdict,
)
from pricepilot.logging import get_logger

log = get_logger("agents.sibt")

BUY_THRESHOLD = 65.0


async def node(state: AgentState) -> AgentState:
    verdicts = dict(state.sibt)
    now = datetime.now(UTC)

    for product in state.canonical_products:
        pid = product["product_id"]
        deal = state.deal_scores.get(pid)
        seller = state.seller_analysis.get(pid)
        price = state.price_analysis.get(pid)

        has_price = price is not None and price.lowest_offer is not None
        deal_score = deal.score if deal else None
        seller_bad = (
            seller is None or seller.label == SellerSignalLabel.INSUFFICIENT_DATA
        )

        reasons: list[str] = []
        verdict: SibtVerdict
        confidence = 0.0

        if has_price and deal_score is not None and not seller_bad and deal_score >= BUY_THRESHOLD:
            verdict = SibtVerdict.BUY
            reasons.append(f"current price {_fmt(price.lowest_offer)} present")
            reasons.append(f"deal score {deal_score:.0f}/100")
            reasons.append("seller signal verified")
            confidence = min(0.9, 0.55 + (deal_score - BUY_THRESHOLD) / 100.0)
        elif has_price:
            verdict = SibtVerdict.WAIT
            reasons.append(f"price {_fmt(price.lowest_offer)} present but")
            if deal_score is not None and deal_score < BUY_THRESHOLD:
                reasons.append(f"deal score {deal_score:.0f}/100 is weak")
            if seller_bad:
                reasons.append("seller confidence is limited or insufficient")
            confidence = 0.5
        elif not has_price and deal_score is None:
            verdict = SibtVerdict.INSUFFICIENT_DATA
            reasons.append("no verified price and no deal score — cannot judge")
            confidence = 0.0
        else:
            verdict = SibtVerdict.AVOID
            reasons.append("price unavailable and seller confidence insufficient")
            reasons.append("no strong evidence this is a good purchase")
            confidence = 0.3

        verdicts[pid] = ShouldIBuy(
            product_id=pid,
            verdict=verdict,
            reasons=reasons,
            confidence=round(confidence, 2),
            generated_at=now,
        )
    return state.model_copy(update={"sibt": verdicts})


def _fmt(value: float) -> str:
    return f"{value:.2f}"