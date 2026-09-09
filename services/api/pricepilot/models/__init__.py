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
    sibt: dict[str, Any] = Field(default_factory=dict)
    forecasts: dict[str, Any] = Field(default_factory=dict)
    research_evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    provider_errors: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    answer: str | None = None
    # Chat additions (Phase 4)
    session_id: str | None = None
    conversation: list[dict[str, Any]] = Field(default_factory=list)
    semantic: str = "keyword"  # "available" | "keyword" (honest status)
    refinements: list[dict[str, Any]] = Field(default_factory=list)


class ChatQuery(BaseModel):
    """Request body for POST /api/v1/shopping/chat."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(default=None, description="Existing chat session, or None to start a new one.")


class ImageSearchQuery(BaseModel):
    """Request body for POST /api/v1/shopping/image (multipart handled separately)."""

    model_config = ConfigDict(extra="forbid")

    max_matches: int = Field(default=3, ge=1, le=10)


# --------------------------------------------------------------------------- #
# Phase 5: price monitoring / tracking / alerts
# --------------------------------------------------------------------------- #


class TrackCreate(BaseModel):
    """Create a watchlist entry for a product."""

    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=64)
    target_price: float | None = Field(default=None, ge=0)
    target_currency: str | None = Field(default=None, max_length=3)
    alert_preferences: dict[str, bool] | None = Field(default=None, max_length=16)


class TrackUpdate(BaseModel):
    """Update a watchlist entry (target, preferences)."""

    model_config = ConfigDict(extra="forbid")

    target_price: float | None = Field(default=None, ge=0, description="Set to change; omit to leave unchanged. Use 0 to clear.")
    target_currency: str | None = Field(default=None, max_length=3)
    alert_preferences: dict[str, bool] | None = Field(default=None, max_length=16)
    paused: bool | None = Field(default=None)


class AlertRead(BaseModel):
    """Mark one or all notifications as read/dismissed."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^(read|dismissed)$")


class PriceHistoryResponse(BaseModel):
    """A product's real observation history + analytics."""

    model_config = ConfigDict(extra="ignore")

    product_id: str
    observations: list[dict[str, Any]] = Field(default_factory=list)
    analytics: dict[str, Any] = Field(default_factory=dict)
    currency: str | None = None


class MonitoringStatusResponse(BaseModel):
    """Honest monitoring capability state."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool
    provider: str  # "available" | "unavailable"
    interval_seconds: int
    tracked_products: int = 0
    message: str | None = None


class UserPreferencesUpdate(BaseModel):
    """Partial update for a user's shopping preferences (Settings page).

    The `user_preferences` table stores the full preference set; any subset of
    fields may be provided. `max_budget` uses 0 to clear — matching the
    TrackUpdate convention. Extra fields are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    preferred_brands: list[str] | None = Field(default=None, max_length=50)
    max_budget: float | None = Field(default=None, ge=0, description="Use 0 to clear budget.")
    min_specs: dict[str, Any] | None = Field(default=None, max_length=32)
    preferred_stores: list[str] | None = Field(default=None, max_length=50)
    preferred_condition: list[str] | None = Field(default=None, max_length=10)
    price_vs_quality: float | None = Field(default=None, ge=0, le=1)
    currency_code: str | None = Field(default=None, max_length=3)
    shopping_locale: str | None = Field(default=None, max_length=16)