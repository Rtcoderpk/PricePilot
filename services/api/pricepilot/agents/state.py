"""Typed agent state for the PricePilot shopping intelligence graph.

Every agent node reads and writes this single structured state (Pydantic). No
`dict[str, Any]` is used as the primary architecture. Missing/unknown data is
represented as `None` / explicit `*_unavailable` markers — never invented.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 (runtime type for Pydantic fields)
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pricepilot.models import RawOffer  # noqa: TC001 (runtime type for Pydantic fields)

# --------------------------------------------------------------------------- #
# Intent
# --------------------------------------------------------------------------- #


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    INR = "INR"
    OTHER = "OTHER"


class Condition(str, Enum):
    NEW = "new"
    REFURBISHED = "refurbished"
    USED = "used"
    ANY = "any"
    UNKNOWN = "unknown"


class RankingPreference(str, Enum):
    BEST_VALUE = "best_value"
    CHEAPEST = "cheapest"
    HIGHEST_RATED = "highest_rated"
    BEST_DEAL = "best_deal"
    UNSPECIFIED = "unspecified"


class Urgency(str, Enum):
    NOW = "now"
    SOON = "soon"
    LATER = "later"
    UNSPECIFIED = "unspecified"


class ShoppingIntent(BaseModel):
    """Structured representation of the user's shopping request.

    Every field is nullable/none unless the user (or a reliable signal)
    supplied it. Never invent.
    """

    model_config = ConfigDict(extra="ignore")

    # The raw query; not parsed but kept for provenance.
    raw_query: str = ""

    category: str | None = None          # e.g. "Television"
    product_type: str | None = None      # e.g. "QLED TV"
    brands: list[str] = Field(default_factory=list)
    budget_min: float | None = None
    budget_max: float | None = None
    currency: str | None = None
    country: str | None = None
    required_features: list[str] = Field(default_factory=list)
    preferred_features: list[str] = Field(default_factory=list)
    excluded_features: list[str] = Field(default_factory=list)
    quantity: int | None = None
    condition: Condition = Condition.UNKNOWN
    use_case: str | None = None          # e.g. "gaming"
    ranking_preference: RankingPreference = RankingPreference.UNSPECIFIED
    urgency: Urgency = Urgency.UNSPECIFIED
    explicit_preferences: list[str] = Field(default_factory=list)

    # Fields the parser flagged as ambiguous/uncertain so downstream agents don't
    # assume they are certain.
    uncertain_fields: list[str] = Field(default_factory=list)

    @property
    def has_hard_budget(self) -> bool:
        return self.budget_max is not None


# --------------------------------------------------------------------------- #
# Analysis structures
# --------------------------------------------------------------------------- #


class SourceRef(BaseModel):
    """Provenance for a claim/fact."""

    model_config = ConfigDict(extra="ignore")

    source: str
    provider: str | None = None
    url: str | None = None
    timestamp: datetime | None = None


class ResearchEvidence(BaseModel):
    """Real, sourced facts about a product. Missing fields stay null."""

    model_config = ConfigDict(extra="ignore")

    product_id: str
    name: str
    brand: str | None = None
    category: str | None = None
    quantity: str | None = None
    storage: str | None = None
    image_url: str | None = None
    identifiers: list[dict[str, str]] = Field(default_factory=list)
    offer_count: int = 0
    sources: list[SourceRef] = Field(default_factory=list)


class PricePosition(str, Enum):
    BELOW_AVERAGE = "below_historical_average"
    AROUND_AVERAGE = "around_historical_average"
    ABOVE_AVERAGE = "above_historical_average"
    INSUFFICIENT_HISTORY = "insufficient_history"
    NO_PRICE = "no_price"


class PriceAnalysis(BaseModel):
    """Real price analysis for a canonical product."""

    model_config = ConfigDict(extra="ignore")

    product_id: str
    lowest_offer: float | None = None
    highest_offer: float | None = None
    average_offer: float | None = None
    offer_count: int = 0
    currency: str | None = None
    price_timestamp: datetime | None = None
    shipping_cost: float | None = None
    total_known_cost: float | None = None
    # Only set when enough history exists; otherwise INSUFFICIENT_HISTORY.
    price_position: PricePosition = PricePosition.INSUFFICIENT_HISTORY
    sources: list[SourceRef] = Field(default_factory=list)


class ReviewAnalysis(BaseModel):
    """Review themes from REAL reviews only."""

    model_config = ConfigDict(extra="ignore")

    product_id: str
    status: str = "review_data_unavailable"  # or "available"
    positive_themes: list[str] = Field(default_factory=list)
    negative_themes: list[str] = Field(default_factory=list)
    common_complaints: list[str] = Field(default_factory=list)
    common_strengths: list[str] = Field(default_factory=list)
    sentiment_summary: str | None = None
    review_count: int = 0
    review_freshness: str | None = None
    confidence: str | None = None  # high|medium|low (honest)
    source_refs: list[SourceRef] = Field(default_factory=list)


class SellerSignalLabel(str, Enum):
    VERIFIED_SIGNAL = "verified_signal"
    LIMITED_INFORMATION = "limited_information"
    INSUFFICIENT_DATA = "insufficient_data"


class SellerAnalysis(BaseModel):
    """Seller confidence from real available signals only."""

    model_config = ConfigDict(extra="ignore")

    product_id: str
    seller_name: str | None = None
    label: SellerSignalLabel = SellerSignalLabel.INSUFFICIENT_DATA
    signals: list[str] = Field(default_factory=list)
    offer_availability: bool | None = None
    price_consistency: str | None = None  # stable|variable|unknown
    shipping_info: str | None = None
    warranty_info: str | None = None
    reason: str | None = None


class DealScore(BaseModel):
    """Explainable deal score derived from real signals."""

    model_config = ConfigDict(extra="ignore")

    product_id: str
    score: float | None = None  # 0..100, None when insufficient data
    label: str = "Insufficient Data"
    components: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    missing_data_warnings: list[str] = Field(default_factory=list)


class SibtVerdict(str, Enum):
    BUY = "buy"
    WAIT = "wait"
    AVOID = "avoid"
    INSUFFICIENT_DATA = "insufficient_data"


class ShouldIBuy(BaseModel):
    """Explainable BUY / WAIT / AVOID verdict from real signals."""

    model_config = ConfigDict(extra="ignore")

    product_id: str
    verdict: SibtVerdict = SibtVerdict.INSUFFICIENT_DATA
    reasons: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    generated_at: datetime | None = None


class ForecastStatus(str, Enum):
    INSUFFICIENT_HISTORY = "insufficient_history"
    AVAILABLE = "available"


class ForecastAnalysis(BaseModel):
    """Uncertainty-aware price estimate. NEVER a guarantee."""

    model_config = ConfigDict(extra="ignore")

    product_id: str
    status: ForecastStatus = ForecastStatus.INSUFFICIENT_HISTORY
    method: str | None = None
    forecast_next: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    confidence: float | None = None  # 0..1
    samples: int = 0
    reason: str | None = None


class Recommendation(BaseModel):
    """A ranked recommendation with explainable reasons."""

    model_config = ConfigDict(extra="ignore")

    product_id: str
    product_name: str
    rank: int | None = None
    matches_hard_constraints: bool = True
    reasons: list[str] = Field(default_factory=list)
    deal_score: float | None = None
    best_price: float | None = None
    currency: str | None = None
    url: str | None = None
    image_url: str | None = None
    match_confidence: float | None = None


# --------------------------------------------------------------------------- #
# Run/state
# --------------------------------------------------------------------------- #


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class AgentState(BaseModel):
    """The shared typed state threaded through the agent graph."""

    model_config = ConfigDict(extra="ignore")

    request_id: str
    user_id: str | None = None
    original_query: str

    intent: ShoppingIntent | None = None
    search_queries: list[str] = Field(default_factory=list)
    candidate_offers: list[RawOffer] = Field(default_factory=list)

    canonical_products: list[dict[str, Any]] = Field(default_factory=list)

    research_evidence: dict[str, ResearchEvidence] = Field(default_factory=dict)
    price_analysis: dict[str, PriceAnalysis] = Field(default_factory=dict)
    review_analysis: dict[str, ReviewAnalysis] = Field(default_factory=dict)
    seller_analysis: dict[str, SellerAnalysis] = Field(default_factory=dict)
    deal_scores: dict[str, DealScore] = Field(default_factory=dict)
    sibt: dict[str, ShouldIBuy] = Field(default_factory=dict)
    forecasts: dict[str, ForecastAnalysis] = Field(default_factory=dict)
    recommendations: list[Recommendation] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)
    provider_errors: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    final_answer: str | None = None

    status: RunStatus = RunStatus.RUNNING
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def running(self) -> bool:
        return self.status == RunStatus.RUNNING

    @property
    def product_ids(self) -> list[str]:
        return [p.get("product_id") or p.get("canonical_product_id") for p in self.canonical_products]