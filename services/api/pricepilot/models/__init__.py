"""Domain models (Pydantic) used by the provider stack and API layer.

These are transport/response schemas, validated on every boundary crossing.
Raw provider data is normalized into these models before it is returned.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from datetime import datetime


class ProviderAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ProductIdentifierRef(BaseModel):
    """A structured identifier (GTIN/EAN/UPC, MPN, model, sku...)."""

    model_config = ConfigDict(extra="ignore")

    type: str
    value: str


class RawOffer(BaseModel):
    """An offer as fetched from a provider, before normalization/matching.

    `data_source` names the provider; `is_fixture` flags dev-only demo data.
    `identifiers` and `attributes` are the normalized, structured view used by
    the canonical matcher.
    """

    model_config = ConfigDict(extra="ignore")

    provider: str
    title: str
    url: str | None = None
    price_amount: float | None = None
    price_currency: str = "USD"
    availability: str | None = None
    data_source: str = "provider"
    is_fixture: bool = False
    brand: str | None = None
    model: str | None = None
    quantity: str | None = None
    storage: str | None = None
    color: str | None = None
    identifiers: list[ProductIdentifierRef] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class PriceInsight(BaseModel):
    """Aggregate price view for a product, derived ONLY from recorded data."""

    model_config = ConfigDict(extra="ignore")

    current: float | None = None
    lowest_90d: float | None = None
    avg_90d: float | None = None
    currency: str = "USD"
    sample_count: int = 0


class ProductResult(BaseModel):
    """A canonical product with its merchant offers and derived insight.

    One product = one variant + many merchant offers (deduplicated). `variant`
    holds the distinguishing attributes (storage, quantity, color, ...).
    `match_confidence`/`match_method` explain how offers were grouped.
    """

    model_config = ConfigDict(extra="ignore")

    canonical_product_id: str
    name: str
    brand: str | None = None
    category: str | None = None
    description: str | None = None
    image_url: str | None = None
    variant: dict[str, Any] = Field(default_factory=dict)
    match_confidence: float = 1.0
    match_method: str = "provider"
    offers: list[RawOffer] = Field(default_factory=list)
    price_insight: PriceInsight | None = None
    is_fixture: bool = False


class ProviderStatus(BaseModel):
    """Declared capability state of a provider slot, surfaced to the UI."""

    model_config = ConfigDict(extra="ignore")

    name: str
    availability: ProviderAvailability
    reason: str | None = None


class SearchResponse(BaseModel):
    """The full search result envelope returned to clients."""

    model_config = ConfigDict(extra="ignore")

    query: str
    products: list[ProductResult] = Field(default_factory=list)
    providers: list[ProviderStatus] = Field(default_factory=list)
    total: int = Field(default=0, description="Number of products returned")
    generated_at: datetime | None = None
    notice: str | None = Field(
        default=None,
        description="Human-readable note for the UI (e.g. demo-mode or partial-provider warning).",
    )


class SearchQuery(BaseModel):
    """Request body for POST /api/v1/search."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=20, ge=1, le=100)


class HealthStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str = "ok"
    app_version: str = "0.1.0"
    database: str = "ok"
    redis: str = "ok"
    search_provider: str
    search_provider_available: bool


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    message: str
    details: Any | None = None


class ShoppingSearchQuery(BaseModel):
    """Request body for POST /api/v1/shopping/search."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    use_llm: bool = Field(default=True, description="Allow LLM intent parsing (falls back to deterministic parser when unavailable).")


class ShoppingSearchResponse(BaseModel):
    """The full agent answer envelope for a shopping search."""

    model_config = ConfigDict(extra="ignore")

    request_id: str
    query: str
    status: str  # running|completed|partial|failed
    intent: dict[str, Any] | None = None
    products: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    price_analysis: dict[str, Any] = Field(default_factory=dict)
    review_analysis: dict[str, Any] = Field(default_factory=dict)
    seller_analysis: dict[str, Any] = Field(default_factory=dict)
    deal_scores: dict[str, Any] = Field(default_factory=dict)
    research_evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    provider_errors: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    answer: str | None = None