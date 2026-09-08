"""Search agent: intent → optimized query → concurrent provider queries.

Reuses configured SearchProviders (Phase 1/2) and runs them concurrently with
per-provider timeouts. Returns the raw offers collected. Matching/canonicalization
is a separate node that reuses the Phase 2 engine.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pricepilot.logging import get_logger
from pricepilot.providers.registry import build_providers
from pricepilot.providers.search import NoopSearchProvider

if TYPE_CHECKING:
    from pricepilot.agents.state import AgentState

log = get_logger("agents.search")

PROVIDER_TIMEOUT_SECONDS = 20


def derive_queries(intent) -> list[str]:
    """Build an optimized query string from structured intent."""
    parts: list[str] = []
    if intent.brands:
        parts.append(" ".join(intent.brands[:2]))
    if intent.category:
        parts.append(intent.category)
    elif intent.product_type:
        parts.append(intent.product_type)
    query = " ".join(parts).strip()
    return [query] if query else ["top products"]


async def node(state: AgentState) -> AgentState:
    intent = state.intent or None
    queries = derive_queries(intent) if intent else ["top products"]
    providers = [p for p in build_providers() if not isinstance(p, NoopSearchProvider)]

    if not providers:
        return state.model_copy(
            update={
                "search_queries": queries,
                "provider_errors": state.provider_errors + ["No search provider configured"],
                "warnings": state.warnings + ["Search provider is not configured"],
            }
        )

    per_provider = max(1, 10 // len(providers))

    async def _one(provider) -> list:
        try:
            return await asyncio.wait_for(
                provider.search(queries[0], max_results=per_provider),
                timeout=PROVIDER_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            log.warning("agent search timed out for provider %s", provider.name)
            return []
        except Exception:
            log.exception("agent search failed for provider %s", provider.name)
            return []

    batched = await asyncio.gather(*(_one(p) for p in providers))
    offers = [offer for batch in batched for offer in batch]

    return state.model_copy(
        update={
            "search_queries": queries,
            "candidate_offers": offers,
            "provider_errors": state.provider_errors
            + ([f"provider {p.name} returned no offers" for p, b in zip(providers, batched, strict=False) if not b and not isinstance(p, NoopSearchProvider)]),
        }
    )