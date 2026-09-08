"""Price forecasting agent — uncertainty-aware, history-gated.

Only produces a forecast when the product has at least MIN_SAMPLES real
`prices` rows. Otherwise returns `status=insufficient_history` explicitly.
Methodology: simple linear trend over real (recorded_at, amount) points, with a
range from the residual standard deviation. Always framed as an estimate, never
a guarantee.
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime

from sqlalchemy import text

from pricepilot.agents.state import AgentState, ForecastAnalysis, ForecastStatus
from pricepilot.logging import get_logger

log = get_logger("agents.forecast")

MIN_SAMPLES = 30
CONFIDENCE_LEVEL = 0.80


async def node(state: AgentState, *, session=None) -> AgentState:
    if session is None:
        return _honest_insufficient(state)

    forecasts = dict(state.forecasts)
    for product in state.canonical_products:
        pid = product["product_id"]
        points = await _load_history(session, pid)
        if len(points) < MIN_SAMPLES:
            forecasts[pid] = ForecastAnalysis(
                product_id=pid,
                status=ForecastStatus.INSUFFICIENT_HISTORY,
                samples=len(points),
                reason=f"need at least {MIN_SAMPLES} real price samples; have {len(points)}",
            )
            continue

        forecast = _linear_trend_forecast(pid, points)
        forecasts[pid] = forecast
    return state.model_copy(update={"forecasts": forecasts})


async def _load_history(session, product_id: str) -> list[tuple[float, float]]:
    """Return [(days_ago, amount)] from the `prices` table for a product."""
    try:
        result = await session.execute(
            text(
                "SELECT amount, recorded_at FROM prices "
                "WHERE product_id = :pid AND amount IS NOT NULL "
                "ORDER BY recorded_at ASC"
            ),
            {"pid": product_id},
        )
        rows = result.fetchall()
    except Exception:
        log.exception("forecast history query failed for %s", product_id)
        return []

    base = datetime.now(UTC)
    points = []
    for row in rows:
        amount = float(row.amount)
        recorded = row.recorded_at
        if recorded is None:
            continue
        aware = recorded if getattr(recorded, "tzinfo", None) else recorded.replace(tzinfo=UTC)
        days_ago = (base - aware).total_seconds() / 86400.0
        points.append((days_ago, amount))
    return points


def _linear_trend_forecast(product_id: str, points: list[tuple[float, float]]) -> ForecastAnalysis:
    """Simple linear fit: price ~ a + b*days_ago, forecast next 7 days.

    Returns a range via residual standard deviation, honest about uncertainty.
    """
    n = len(points)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)
    denom = sum((x - mean_x) ** 2 for x in xs)
    b = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=False)) / denom if denom else 0.0
    a = mean_y - b * mean_x

    forecast_days = 7
    forecast_next = max(0.0, a + b * (min(xs) - forecast_days))  # extrapolate into the future

    residuals = [y - (a + b * x) for x, y in points]
    sigma = statistics.stdev(residuals) if n > 1 else 0.0
    # 80% ~ 1.28 sigma each side
    spread = 1.28 * sigma

    return ForecastAnalysis(
        product_id=product_id,
        status=ForecastStatus.AVAILABLE,
        method="linear_trend",
        forecast_next=round(forecast_next, 2),
        lower_bound=round(max(0.0, forecast_next - spread), 2),
        upper_bound=round(forecast_next + spread, 2),
        confidence=round(CONFIDENCE_LEVEL, 2),
        samples=n,
        reason="linear trend over real price history; estimate, not a guarantee",
    )


def _honest_insufficient(state: AgentState) -> AgentState:
    forecasts = dict(state.forecasts)
    for product in state.canonical_products:
        pid = product["product_id"]
        forecasts[pid] = ForecastAnalysis(
            product_id=pid, status=ForecastStatus.INSUFFICIENT_HISTORY,
            reason=f"need at least {MIN_SAMPLES} real price samples",
        )
    return state.model_copy(update={"forecasts": forecasts})