"""Review provider registry (`PRICEPILOT_REVIEW_PROVIDER`).

Until a marketplace review API is configured, returns the honest no-op so the
review agent reports `review_data_unavailable`.
"""

from __future__ import annotations

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.providers.reviews import NoopReviewProvider, ReviewProvider

log = get_logger("providers.reviews.registry")


def build_review_provider() -> ReviewProvider:
    names = [n.strip().lower() for n in (settings.pricepilot_review_provider or "").split(",") if n.strip()]
    if names:
        log.warning("review provider %r requested but not yet implemented; using honest no-op", names)
    return NoopReviewProvider()