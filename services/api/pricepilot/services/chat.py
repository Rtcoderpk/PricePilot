"""Multi-turn shopping chat service.

Manages `shopping_sessions` (messages + applied_filters, persisted), runs the
shopping agent graph for each user turn, applies deterministic refinements
(from `chat_refine`), and returns the agent response with conversation context.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from pricepilot.agents.chat_refine import parse_refinement
from pricepilot.agents.graph import run_shopping_agent
from pricepilot.agents.state import AgentState, RunStatus
from pricepilot.db import SessionLocal
from pricepilot.logging import get_logger

log = get_logger("services.chat")


async def run_chat(
    *,
    request_id: str,
    query: str,
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Process one chat turn: load/create session, refine, run graph, persist.

    Ownership: a client-supplied `session_id` is only honored when it belongs to
    this `user_id` (or to the anonymous legacy pool when `user_id` is None).
    Cross-user sessions are never loaded — the caller gets a not_found result.
    """
    async with SessionLocal() as db:
        sid = session_id or await _create_session(db, query, user_id)
        if session_id and not await _session_belongs_to(db, session_id, user_id or ""):
            log.warning("chat session %s requested but not owned by %s", session_id, user_id)
            return {
                "status": "not_found",
                "session_id": session_id,
                "query": query,
                "answer": None,
                "conversation": [],
                "warnings": ["Session not found or not owned by this user."],
                "products": [],
                "recommendations": [],
            }
        # load existing filters/messages for context
        filters, messages = await _load_session(db, sid, user_id=user_id)

        # try to parse as a refinement of an ongoing conversation
        refinement = parse_refinement(query)
        if refinement.applied and filters:
            note = refinement.note or "Refinement applied."
            updated_filters = await _apply_refinement(db, sid, filters, refinement, note, user_id=user_id)
        else:
            updated_filters = filters

        # run the shopping graph (fresh search each turn; filters applied downstream)
        state = await run_shopping_agent(
            request_id=request_id,
            query=query,
            user_id=user_id,
            session=db,
            use_llm=True,
        )

        # apply session filters to the produced recommendations (brand allowlist,
        # budget, condition) before returning.
        state = _apply_session_filters(state, updated_filters)

        user_msg = {"role": "user", "text": query, "ts": _now_iso()}
        assistant_msg = {
            "role": "assistant",
            "text": state.final_answer or "I couldn't find anything to recommend.",
            "ts": _now_iso(),
        }
        messages = messages + [user_msg, assistant_msg]
        await _append_messages(db, sid, messages, user_id=user_id)
        await _update_session_status(db, sid, _status_of(state), user_id=user_id)

        return {
            "status": "ok",
            "session_id": sid,
            "query": query,
            "answer": state.final_answer,
            "conversation": messages,
            "refinement": refinement.note,
            "warnings": state.warnings,
            "products": state.canonical_products,
            "recommendations": [r.model_dump(mode="json") for r in state.recommendations],
            "intent": state.intent.model_dump(mode="json") if state.intent else None,
            "price_analysis": {k: v.model_dump(mode="json") for k, v in state.price_analysis.items()},
            "review_analysis": {k: v.model_dump(mode="json") for k, v in state.review_analysis.items()},
            "seller_analysis": {k: v.model_dump(mode="json") for k, v in state.seller_analysis.items()},
            "deal_scores": {k: (v.model_dump(mode="json") if v else {}) for k, v in state.deal_scores.items()},
            "sibt": {k: (v.model_dump(mode="json") if v else {}) for k, v in state.sibt.items()},
            "forecasts": {k: (v.model_dump(mode="json") if v else {}) for k, v in state.forecasts.items()},
        }


# --------------------------------------------------------------------------- #
# session persistence helpers
# --------------------------------------------------------------------------- #


async def _create_session(db, first_query: str, user_id: str | None) -> str:
    sid = str(uuid.uuid4())
    try:
        await db.execute(
            text(
                "INSERT INTO shopping_sessions (id, user_id, run_id, applied_filters, messages, "
                "status, created_at, updated_at) "
                "VALUES (:id, :uid, NULL, '{}'::jsonb, '[]'::jsonb, 'active', now(), now())"
            ),
            {"id": sid, "uid": user_id},
        )
        await db.commit()
    except Exception:
        log.exception("create chat session failed")
    return sid


def _owner_clause(user_id: str | None = None) -> tuple[str, dict]:
    """Return a SQL owner filter + params. Anonymous legacy sessions are
    `user_id IS NULL`; authenticated sessions must match exactly."""
    if user_id:
        return "AND user_id = :owner", {"owner": user_id}
    return "AND user_id IS NULL", {}


async def _session_belongs_to(db, sid: str, user_id: str | None) -> bool:
    try:
        owner_sql, owner_params = _owner_clause(user_id)
        row = await db.execute(
            text(f"SELECT id FROM shopping_sessions WHERE id = :sid {owner_sql}"),
            {"sid": sid, **owner_params},
        )
        return row.mappings().first() is not None
    except Exception:
        log.exception("chat session ownership check failed")
        return False


async def _load_session(db, sid: str, *, user_id: str | None = None) -> tuple[dict, list[dict]]:
    filters: dict = {}
    messages: list[dict] = []
    try:
        owner_sql, owner_params = _owner_clause(user_id)
        row = await db.execute(
            text(
                "SELECT applied_filters, messages FROM shopping_sessions "
                f"WHERE id = :sid AND status='active' {owner_sql}"
            ),
            {"sid": sid, **owner_params},
        )
        result = row.mappings().first()
        if result:
            filters = dict(result["applied_filters"] or {})
            messages = list(result["messages"] or [])
    except Exception:
        log.exception("load chat session failed")
    return filters, messages


async def _apply_refinement(db, sid: str, filters: dict, refinement, note: str, *, user_id: str | None = None) -> dict:
    updated = dict(filters)
    kind = refinement.kind
    if kind == "brand_allow" and refinement.value:
        updated["brand_allow"] = refinement.value
    elif kind == "brand_block" and refinement.value:
        updated["brand_block"] = refinement.value
    elif kind == "budget" and refinement.value:
        updated["budget_max"] = float(refinement.value)
    elif kind == "condition":
        updated["condition"] = refinement.value
    elif kind == "cheaper":
        updated.setdefault("preferences", {})["cheaper"] = True
    elif kind == "rank":
        updated["ranking"] = refinement.value or "highest_rated"
    elif kind == "more":
        updated["show_more"] = True
    # note already persisted below via the updated filters/messages
    try:
        owner_sql, owner_params = _owner_clause(user_id)
        await db.execute(
            text(
                "UPDATE shopping_sessions SET applied_filters = :filters, updated_at = now() "
                f"WHERE id = :sid {owner_sql}"
            ),
            {"filters": updated, "sid": sid, **owner_params},
        )
        await db.commit()
    except Exception:
        log.exception("apply refinement to session failed")
    return updated


async def _append_messages(db, sid: str, messages: list[dict], *, user_id: str | None = None) -> None:
    try:
        owner_sql, owner_params = _owner_clause(user_id)
        await db.execute(
            text(
                "UPDATE shopping_sessions SET messages = :msgs, updated_at = now() "
                f"WHERE id = :sid {owner_sql}"
            ),
            {"msgs": messages, "sid": sid, **owner_params},
        )
        await db.commit()
    except Exception:
        log.exception("append chat messages failed")


async def _update_session_status(db, sid: str, status: str, *, user_id: str | None = None) -> None:
    try:
        owner_sql, owner_params = _owner_clause(user_id)
        await db.execute(
            text(f"UPDATE shopping_sessions SET status = :st WHERE id = :sid {owner_sql}"),
            {"st": status, "sid": sid, **owner_params},
        )
        await db.commit()
    except Exception:
        log.exception("update chat session status failed")


def _status_of(state: AgentState) -> str:
    return "active" if state.status in (RunStatus.COMPLETED, RunStatus.PARTIAL) else "closed"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _apply_session_filters(state: AgentState, filters: dict) -> AgentState:
    """Apply session filters to recommendations before returning to the user.

    Brand allowlist/blocks, budget override, condition. Filtering happens on the
    recommendation list so the raw product set still reflects the provider search.
    """
    if not filters:
        return state

    recs = list(state.recommendations)
    brand_allow = filters.get("brand_allow")
    brand_block = filters.get("brand_block")
    budget_max = filters.get("budget_max")

    def _matches(rec) -> bool:
        name = (rec.product_name or "").lower()
        blocked = bool(brand_allow and brand_allow.lower() not in name)
        blocked = blocked or bool(brand_block and brand_block.lower() in name)
        blocked = blocked or bool(
            budget_max is not None and (rec.best_price is None or rec.best_price > float(budget_max))
        )
        return not blocked

    filtered = [rec for rec in recs if _matches(rec)]
    if filtered:
        state = state.model_copy(update={"recommendations": filtered})
    return state