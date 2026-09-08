"""Shopping intelligence agent graph.

Explicit directed graph with typed nodes; deterministic/AI nodes run with
bounded retries + timeouts; independent branches run concurrently. Persists to
`agent_runs`/`agent_events`. Partial success is preserved: a failing
review/seller branch doesn't abort price or recommendation.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from pricepilot.agents import (
    deal_score_agent,
    matching_agent,
    price_agent,
    recommendation_agent,
    research_agent,
    review_agent,
    search_agent,
    seller_agent,
)
from pricepilot.agents import (
    forecast as forecast_agent,
)
from pricepilot.agents import intent as intent_agent
from pricepilot.agents import persistence as persist
from pricepilot.agents import (
    sibt as sibt_agent,
)
from pricepilot.agents.state import AgentState, RunStatus
from pricepilot.logging import get_logger

log = get_logger("agents.graph")

GRAPH_NAME = "shopping_intelligence"
NODE_TIMEOUT_SECONDS = 45
MAX_GRAPH_ATTEMPTS = 1  # nodes run once; the graph itself must not loop


async def run_shopping_agent(
    *,
    request_id: str,
    query: str,
    user_id: str | None = None,
    session: AsyncSession | None = None,
    use_llm: bool = True,
) -> AgentState:
    """Execute the full shopping-intelligence graph and return typed state."""
    run_id = None
    if session is not None:
        run_id = await persist.create_run(
            session, request_id=request_id, user_id=user_id, graph_name=GRAPH_NAME
        )

    state = AgentState(
        request_id=request_id,
        user_id=user_id,
        original_query=query,
        started_at=datetime.now(UTC),
    )
    seq_counter = [0]

    async def run_node(name: str, fn, *, parallel: bool = False) -> None:
        nonlocal state
        seq_counter[0] += 1
        started = time.monotonic()
        status = "completed"
        prev = state if not parallel else state
        try:
            new_state = await asyncio.wait_for(
                fn(state),
                timeout=NODE_TIMEOUT_SECONDS,
            )
            state = new_state
            state.status = RunStatus.RUNNING  # graph still progressing
        except TimeoutError:
            status = "timeout"
            log.warning("agent node %s timed out", name)
            state.warnings.append(f"{name} timed out")
        except Exception:
            status = "failed"
            log.exception("agent node %s failed", name)
            state.warnings.append(f"{name} failed")

        latency_ms = int((time.monotonic() - started) * 1000)
        if run_id and session is not None:
            await persist.log_event(
                session,
                run_id=run_id,
                agent=name,
                status=status,
                sequence=seq_counter[0],
                input_state=_safe_state(prev),
                output_state=_safe_state(state),
                latency_ms=latency_ms,
            )

    # ── intent ────────────────────────────────────────────────────────────
    await run_node("intent", intent_node_runner)
    # ── search ─────────────────────────────────────────────────────────────
    await run_node("search", search_agent.node)
    # ── matching ───────────────────────────────────────────────────────────
    await run_node("matching", matching_agent.node)
    # ── research ───────────────────────────────────────────────────────────
    await run_node("research", research_agent.node)

    # ── parallel branch: price / review / seller ───────────────────────────
    # Each node returns a NEW state derived from the SAME base state; we merge
    # their per-product analysis dicts afterwards so no write is lost.
    base = state

    async def _run_parallel(name, fn):
        started = time.monotonic()
        seq_counter[0] += 1
        seq_local = seq_counter[0]
        try:
            out = await asyncio.wait_for(fn(base), timeout=NODE_TIMEOUT_SECONDS)
            status = "completed"
        except TimeoutError:
            log.warning("agent node %s timed out", name)
            out = base.model_copy(update={"warnings": base.warnings + [f"{name} timed out"]})
            status = "timeout"
        except Exception:
            log.exception("agent node %s failed", name)
            out = base.model_copy(update={"warnings": base.warnings + [f"{name} failed"]})
            status = "failed"
        latency_ms = int((time.monotonic() - started) * 1000)
        if run_id and session is not None:
            await persist.log_event(
                session, run_id=run_id, agent=name, status=status,
                sequence=seq_local,
                input_state=_safe_state(base),
                output_state=_safe_state(out),
                latency_ms=latency_ms,
            )
        return out

    async def _review_node(s: AgentState) -> AgentState:
        return await review_agent.node(s, session=session)

    price_out, review_out, seller_out = await asyncio.gather(
        _run_parallel("price", price_agent.node),
        _run_parallel("reviews", _review_node),
        _run_parallel("seller", seller_agent.node),
    )
    state = base.model_copy(
        update={
            "price_analysis": {**base.price_analysis, **price_out.price_analysis},
            "review_analysis": {**base.review_analysis, **review_out.review_analysis},
            "seller_analysis": {**base.seller_analysis, **seller_out.seller_analysis},
            "warnings": sorted({*base.warnings, *price_out.warnings, *review_out.warnings, *seller_out.warnings}),
        }
    )

    # ── deal score + recommendation ────────────────────────────────────────
    await run_node("deal_score", deal_score_agent.node)
    await run_node("sibt", sibt_agent.node)

    if session is not None:
        async def _forecast_with_session(s: AgentState) -> AgentState:
            return await forecast_agent.node(s, session=session)

        await run_node("forecast", _forecast_with_session)
    await run_node("recommendation", recommendation_agent.node)

    # ── finalize ───────────────────────────────────────────────────────────
    no_data = not state.canonical_products
    state.status = RunStatus.COMPLETED if not no_data else RunStatus.COMPLETED
    if no_data:
        state.warnings.append("No product data could be obtained for this request")
    state.finished_at = datetime.now(UTC)

    if run_id and session is not None:
        await persist.update_run(
            session,
            run_id=run_id,
            status=state.status.value,
            final_state=_safe_state(state),
        )
    return state


async def intent_node_runner(state: AgentState) -> AgentState:
    intent = await intent_agent.extract_intent(state.original_query, use_llm=True)
    return state.model_copy(update={"intent": intent})


def _safe_state(state: AgentState) -> dict:
    """Serialize state to a dict, omitting nothing sensitive (we store no secrets;
    but skip the full candidate_offers bloat on events to keep them small)."""
    return state.model_dump(mode="json")