"""Supplier product-research pipeline (Phase on top of the agent graph).

Chains deterministic services: input router → product understanding → search →
verification → comparison → recommendation → response. Only Gemini is used
where genuinely required (image understanding); everything else is deterministic
so results are fast, cheap, testable, and never hallucinated.

The pipeline never treats the LLM as a source of truth for supplier/price/MOQ/
shipping data — those come only from retrieved provider/source data.
"""