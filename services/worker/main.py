"""Background worker (Phase 5): price monitoring + alert detection loop.

Cycle (with bounded concurrency, timeouts, retry/backoff, provider failure
isolation, and honest unavailable states):

1. If `MONITOR_ENABLED` is false or the provider reports unavailable, log
   `monitoring_unavailable` and stay idle.
2. Load active (non-paused) watchlist entries that have an observable product
   (canonical product + barcode).
3. Poll each offer concurrently (`monitor_max_concurrency`), with a per-provider
   timeout, persisting real observations and running deterministic price-event
   detection + alert creation.
4. One offer's failure must not abort the cycle.

Idempotency: observations are deduped within `MONITOR_OBSERVATION_WINDOW_SECONDS`
so we never re-write the same unchanged price repeatedly; alerts are deduped by
`event_key`.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
import time

from sqlalchemy import text

from pricepilot.config import settings
from pricepilot.db import SessionLocal
from pricepilot.logging import get_logger
from pricepilot.monitoring.price_source import PriceSource, price_source_status

log = get_logger("worker")


async def _load_tracked_offers(session) -> list[dict]:
    """Load active watchlist entries that map to a real product + barcode."""
    try:
        rows = (await session.execute(
            text(
                "SELECT w.id AS watchlist_id, w.user_id, w.product_id, w.target_price, "
                "w.target_currency, w.alert_preferences, "
                "pi.id_value AS barcode, "
                "(SELECT o.id FROM product_offers o WHERE o.product_id = w.product_id "
                " ORDER BY o.last_seen_at DESC NULLS LAST LIMIT 1) AS offer_id "
                "FROM watchlists w "
                "JOIN product_identifiers pi ON pi.product_id = w.product_id "
                " AND pi.id_type IN ('gtin','ean','upc') "
                "WHERE w.paused = false "
                "ORDER BY w.created_at"
            )
        )).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        log.exception("worker: load tracked offers failed")
        return []


async def _fetch_with_retry(source: PriceSource, barcode: str):
    """Fetch a price with bounded retry/backoff on transient provider failures.

    A `no_price` (valid response, no price in it) is not retried — only provider
    errors/outages are, because a 404/product-absent is a definitive answer.
    """
    attempts = max(0, settings.monitor_retry_count) + 1
    for attempt in range(attempts):
        result = await source.fetch_current_price(barcode)
        if result.status != "provider_failed":
            return result
        if attempt + 1 < attempts:
            await asyncio.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s, ...
    return result


async def _process_one(session, source: PriceSource, entry: dict) -> dict:
    """Poll one watchlist entry, persisting observations + creating alerts.

    Provider fetch is retried up to `monitor_retry_count` times with a short
    backoff (a transient outage on one offer must not abort the cycle).
    """
    wl_id = entry["watchlist_id"]
    user_id = entry["user_id"]
    barcode = entry.get("barcode")
    offer_id = entry.get("offer_id")

    if not barcode or not offer_id or not user_id:
        return {"watchlist_id": wl_id, "status": "skipped", "reason": "no offer/user/barcode"}

    # Bound the whole per-entry operation so a stuck provider/poll can never
    # hang the worker beyond a fixed budget (provider timeout + retries + margin).
    entry_budget = max(
        settings.monitor_provider_timeout_seconds,
        settings.monitor_provider_timeout_seconds * (settings.monitor_retry_count + 1) + 10,
    )
    try:
        return await asyncio.wait_for(_poll_entry(session, source, entry, wl_id), timeout=entry_budget)
    except TimeoutError:
        log.warning("worker: entry %s exceeded timeout budget", wl_id)
        return {"watchlist_id": wl_id, "status": "timeout"}


async def _poll_entry(session, source: PriceSource, entry: dict, wl_id: str) -> dict:
    user_id = entry["user_id"]
    product_id = entry["product_id"]
    offer_id = entry.get("offer_id")
    target_price = float(entry["target_price"]) if entry.get("target_price") is not None else None

    result = await _fetch_with_retry(source, entry["barcode"])
    if result.status == "provider_failed":
        return {"watchlist_id": wl_id, "status": "provider_failed"}

    from pricepilot.monitoring import process_service_poll

    # Availability transitions (back-in-stock) are evaluated from the offer row,
    # so we process the poll even when the provider supplies no price; only a
    # provider outage is skipped.
    outcome = await process_service_poll(
        session,
        user_id=str(user_id),
        watchlist_id=str(wl_id),
        product_id=str(product_id),
        offer_id=str(offer_id),
        amount=result.amount,
        currency=result.currency,
        available=result.available,
        source="openfoodfacts",
        target_price=target_price,
        event_scope=f"wl:{wl_id}",
    )
    if result.status == "no_price":
        return {"watchlist_id": wl_id, "status": "no_price", "reason": result.reason, **outcome}
    status = "observed" if outcome.get("observed") else "unchanged"
    return {"watchlist_id": wl_id, "status": status, **outcome}


async def run_monitoring_cycle() -> dict:
    """One full monitoring cycle. Returns a summary (never raises the worker)."""
    if not settings.monitor_enabled:
        return {"status": "monitoring_disabled"}
    if price_source_status() != "available":
        return {"status": "provider_unavailable"}

    source = PriceSource()
    summary: dict = {"status": "ran", "total": 0, "outcomes": [], "observed": 0}
    try:
        async with SessionLocal() as session:
            entries = await _load_tracked_offers(session)
            summary["total"] = len(entries)
            if not entries:
                summary["status"] = "no_tracked_offers"
                return summary

            sem = asyncio.Semaphore(max(1, settings.monitor_max_concurrency))

            async def guarded(entry):
                async with sem:
                    return await _process_one(session, source, entry)

            outcomes = await asyncio.gather(*(guarded(e) for e in entries), return_exceptions=True)
            for o in outcomes:
                if isinstance(o, Exception):
                    summary["outcomes"].append({"status": "exception", "error": str(o)[:120]})
                    log.exception("worker: entry processing raised")
                    continue
                summary["outcomes"].append(o)
                if o.get("observed"):
                    summary["observed"] += 1
            await session.commit()
    except Exception:
        log.exception("worker: monitoring cycle failed (isolated; worker keeps running)")
        summary["status"] = "cycle_failed"
    finally:
        await source.close()
    return summary


async def pump() -> None:
    log.info("worker starting (phase 5 price monitoring)")
    if not settings.monitor_enabled:
        log.info("monitoring disabled via config (MONITOR_ENABLED=false)")
    elif price_source_status() != "available":
        log.info("monitoring unavailable: no real price provider configured")
    else:
        log.info("monitoring available via OpenFoodFacts")


async def main() -> None:
    await pump()

    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        """Graceful shutdown on SIGTERM/SIGINT: finish the current cycle, then exit."""
        log.info("worker: shutdown signal received; finishing current cycle")
        stopping.set()

    for sig in ("SIGTERM", "SIGINT"):
        try:
            loop.add_signal_handler(getattr(signal, sig), _request_stop)
        except (NotImplementedError, RuntimeError, AttributeError):
            # Windows/limited environments may not support signal handlers.
            log.warning("worker: signal handler for %s unavailable", sig)

    interval = max(30, settings.monitor_poll_interval_seconds)
    while not stopping.is_set():
        started = time.monotonic()
        try:
            summary = await run_monitoring_cycle()
            log.info("monitoring cycle: %s (elapsed %.1fs)", summary.get("status"), time.monotonic() - started)
        except Exception:
            log.exception("worker: cycle raised (kept alive)")
        # Await interruptible sleep so a shutdown signal wakes us promptly.
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stopping.wait(), timeout=interval)

    log.info("worker: shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())