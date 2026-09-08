"""Shopping agent service — wires the graph, DB persistence, and response.

`run_shopping` executes the agent graph with a DB session for agent_runs/events
persistence and returns the typed final state + a prepared response.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pricepilot.agents.graph import run_shopping_agent

if TYPE_CHECKING:
    from pricepilot.agents.state import AgentState
from pricepilot.db import SessionLocal
from pricepilot.logging import get_logger

log = get_logger("services.shopping")


class ShoppingAgentService:
    async def run(
        self,
        *,
        request_id: str,
        query: str,
        user_id: str | None = None,
        use_llm: bool = True,
    ) -> AgentState:
        async with SessionLocal() as session:
            return await run_shopping_agent(
                request_id=request_id,
                query=query,
                user_id=user_id,
                session=session,
                use_llm=use_llm,
            )