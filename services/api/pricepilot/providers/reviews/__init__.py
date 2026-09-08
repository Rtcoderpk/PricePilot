"""Review provider contract.

A configured ReviewProvider can fetch real review rows from a marketplace; until
one is configured the review agent returns `review_data_unavailable` (honest).
Never fabricates reviews.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003 (runtime type for ReviewRecord field)

from pricepilot.errors import ProviderUnavailableError


@dataclass
class ReviewRecord:
    product_id: str
    source: str
    external_review_id: str | None = None
    rating: float | None = None
    title: str = ""
    body: str = ""
    author: str | None = None
    review_date: datetime | None = None
    metadata: dict = field(default_factory=dict)


class ReviewProvider(ABC):
    name: str = "reviews"

    @abstractmethod
    async def available(self) -> bool:
        """Whether a review source is configured."""

    @abstractmethod
    async def fetch(self, product_id: str, *, limit: int = 50) -> list[ReviewRecord]:
        """Fetch real review records for a product."""


class NoopReviewProvider(ReviewProvider):
    name = "reviews_unavailable"

    async def available(self) -> bool:
        return False

    async def fetch(self, product_id: str, *, limit: int = 50) -> list[ReviewRecord]:
        raise ProviderUnavailableError("reviews", "No review provider configured (set PRICEPILOT_REVIEW_PROVIDER).")