"""Persistence for agent runs and events.

Writes to `agent_runs` and `agent_events` (existing Phase 1 tables). Best-effort:
a DB failure logs and is swallowed so it never crashes the request.
Never stores API keys, secrets, or raw model prompts.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from pricepilot.logging import get_logger

log = get_logger("agents.persistence")


async def create_run(
    session,
    *,
    request_id: str,
    user_id: str | None,
    graph_name: str,
) -> str:
    run_id = str(uuid.uuid4())
    try:
        await session.execute(
            text(
                "INSERT INTO agent_runs (id, graph_name, status, started_at, created_at) "
                "VALUES (:id, :graph, 'running', now(), now())"
            ),
            {"id": run_id, "graph": graph_name},
        )
        await session.commit()
    except Exception:
        log.exception("create agent_run failed; continuing without persistence")
        with contextlib.suppress(Exception):
            await session.rollback()
    return run_id


async def update_run(
    session,
    *,
    run_id: str,
    status: str,
    error_code: str | None = None,
    final_state: dict | None = None,
) -> None:
    try:
        await session.execute(
            text(
                "UPDATE agent_runs SET status=:status, error_code=:error_code, "
                "final_state=:final_state, finished_at=now() WHERE id=:run_id"
            ),
            {
                "status": status,
                "error_code": error_code,
                "final_state": final_state,
                "run_id": run_id,
            },
        )
        await session.commit()
    except Exception:
        log.exception("update agent_run failed; continuing without persistence")


async def log_event(
    session,
    *,
    run_id: str,
    agent: str,
    status: str,
    sequence: int,
    input_state: dict | None = None,
    output_state: dict | None = None,
    latency_ms: int | None = None,
) -> None:
    try:
        await session.execute(
            text(
                "INSERT INTO agent_events (run_id, sequence, agent, status, "
                "input_state, output_state, latency_ms, created_at) "
                "VALUES (:run_id, :sequence, :agent, :status, :input_state, "
                ":output_state, :latency_ms, now())"
            ),
            {
                "run_id": run_id,
                "sequence": sequence,
                "agent": agent,
                "status": status,
                "input_state": input_state,
                "output_state": output_state,
                "latency_ms": latency_ms,
            },
        )
        await session.commit()
    except Exception:
        log.exception("log agent_event failed; continuing without persistence")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()