"""Background worker entrypoint (Phase 1: health skeleton, no jobs yet).

Long-running jobs (price polling, alerts) land in Phase 5. This process exists
now so the container/workflow topology is real and the worker shares the API's
config, logging, and DB wiring.
"""

from __future__ import annotations

import asyncio

from pricepilot.logging import get_logger

log = get_logger("worker")


async def pump() -> None:
    log.info("worker starting (phase 1 — no jobs configured yet)")


async def main() -> None:
    await pump()
    # Phase 5 wires an alert/price-poll loop here and runs indefinitely.
    while True:
        await asyncio.sleep(60)
        log.debug("worker heartbeat")


if __name__ == "__main__":
    asyncio.run(main())