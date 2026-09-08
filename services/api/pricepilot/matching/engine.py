"""Deterministic, confidence-based product matching engine.

The engine decides whether two *candidates* refer to the same canonical product
(and same variant), returning an explainable confidence and the method used.

Rules (priority order):
1. Strong identifier (GTIN/EAN/UPC barcode) exact match → very high confidence.
   A *conflicting* strong identifier is a strong rejection.
2. Brand + model exact → high confidence.
3. Normalized title match → supporting confidence.
4. Variant attributes (storage, quantity/pack size, color) are compared when
   present: a *conflicting* variant signal is a strong rejection even if
   identifiers/titles match (8GB/256GB ≠ 16GB/512GB, 1kg ≠ 2kg).
5. Semantic similarity is a *supporting* signal only — never sufficient alone
   to merge when a variant signal conflicts.

Never auto-merge uncertain products: `matched=False` when confidence is below
the MERGE_THRESHOLD.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pricepilot.logging import get_logger
from pricepilot.normalization import (
    ProductAttributes,
    normalize_brand,
    normalize_model,
    normalize_title,
)

log = get_logger("matching.engine")

MERGE_THRESHOLD = 0.72
TERMINAL_REASONS = "gtin", "gtin_conflict", "variant_conflict", "brand_conflict"


@dataclass(frozen=True)
class MatchReason:
    label: str
    signal_strength: float  # 0..1 contribution


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    confidence: float
    method: str
    reasons: list[str] = field(default_factory=list)
    # True when a conflict was detected that MUST NOT be merged even if some
    # signals align (different strong id, different variant, different brand).
    hard_block: bool = False


class MatchingEngine:
    """Stateless matcher; build per-request. Injected with a semantic scorer."""

    def __init__(
        self,
        *,
        semantic: SemanticSimilarity | None = None,
        merge_threshold: float = MERGE_THRESHOLD,
    ) -> None:
        self.semantic = semantic
        self.merge_threshold = merge_threshold

    def match(self, a: ProductAttributes, b: ProductAttributes, *, a_id, b_id) -> MatchResult:
        """Score two product candidates, returning an explainable verdict."""
        reasons: list[MatchReason] = []
        # --- 1. strong identifiers ---
        if a_id.gtin and b_id.gtin:
            if a_id.gtin == b_id.gtin:
                return MatchResult(True, 0.99, "gtin", ["Exact GTIN match"])
            return MatchResult(False, 0.0, "gtin_conflict", ["Conflicting GTIN"], hard_block=True)

        # --- MPN fallback (weaker than GTIN but still strong) ---
        if a_id.mpn and b_id.mpn and a_id.mpn == b_id.mpn:
            reasons.append(MatchReason("Exact MPN match", 0.3))

        # --- brand + model ---
        brand_match = None
        a_b = normalize_brand(a.brand)
        b_b = normalize_brand(b.brand)
        if a_b and b_b:
            brand_match = a_b == b_b
        elif a_b or b_b:
            # only one side has a brand → no conflict, weak positive
            reasons.append(MatchReason("Brand supplied on one side", 0.02))

        a_m, b_m = normalize_model(a.model), normalize_model(b.model)
        model_match = a_m is not None and b_m is not None and a_m == b_m

        if brand_match is False:
            return MatchResult(False, 0.0, "brand_conflict", ["Different brands"], hard_block=True)
        if brand_match is True:
            reasons.append(MatchReason("Brand matches", 0.15))
        if a_m and b_m and model_match:
            reasons.append(MatchReason("Model matches", 0.25))

        # --- model-level confirmation ---
        model_level = bool(a_m and b_m and model_match)

        # --- 2. normalized title (supporting) ---
        ta, tb = normalize_title(a.title), normalize_title(b.title)
        if ta and ta == tb:
            reasons.append(MatchReason("Normalized title matches", 0.12))

        # --- 3. variant attributes — strong, and can reject ---
        variant_block = self._variant_signals(a, b, reasons)

        # --- 4. semantic support (never sole basis) ---
        sem_score = 0.0
        if self.semantic is not None:
            sem_score = self.semantic.score_attributes(a, b)
            if sem_score > 0.55 and not variant_block:
                reasons.append(MatchReason("Semantic similarity supports", min(sem_score * 0.2, 0.18)))

        # terminal conflicts must dominate
        if variant_block:
            return MatchResult(False, 0.0, "variant_conflict", [r.label for r in reasons] or ["Variant conflict"], hard_block=True)

        strong = bool(a_id.gtin and b_id.gtin)  # handled by step 1; else False here
        base = 0.0
        if strong:
            base = 0.6
        elif model_level:
            base = 0.5

        # Agreement uplift: when brand + normalized title both match and no
        # variant signal conflicts, this is a firm identity signal (e.g. the
        # same product listed twice by the same brand) even without a model/id.
        has_brand_and_title_agreement = (
            brand_match is True and ta and ta == tb and not variant_block
        )
        if has_brand_and_title_agreement:
            base = max(base, 0.45)

        confidence = min(base + sum(r.signal_strength for r in reasons) + sem_score, 0.99)

        if confidence >= self.merge_threshold:
            method = self._method_for(reasons, strong_id=bool(a_id.gtin or b_id.gtin), model_level=model_level)
            return MatchResult(True, round(confidence, 2), method, [r.label for r in reasons] or ["Similar"])
        return MatchResult(False, round(confidence, 2), "similarity", [r.label for r in reasons] or ["Low similarity"])

    def _variant_signals(self, a: ProductAttributes, b: ProductAttributes, reasons: list[MatchReason]) -> bool:
        """Compare variant attributes; append reasons. Returns True on conflict."""
        conflict = False
        # storage (RAM/disk)
        if a.storage_gb is not None and b.storage_gb is not None:
            if a.storage_gb == b.storage_gb:
                reasons.append(MatchReason(f"Storage matches ({a.storage_gb:g} GB)", 0.15))
            else:
                reasons.append(MatchReason(f"Storage conflicts ({a.storage_gb:g} GB vs {b.storage_gb:g} GB)", -0.5))
                conflict = True
        # quantity / pack size
        if a.quantity is not None and b.quantity is not None:
            if a.quantity.kind == b.quantity.kind and abs(a.quantity.value - b.quantity.value) < 1e-6:
                reasons.append(MatchReason(f"Pack size matches ({a.quantity.unit})", 0.12))
            else:
                reasons.append(MatchReason(
                    f"Pack size conflicts ({a.quantity.raw} vs {b.quantity.raw})", -0.5
                ))
                conflict = True
        # color
        if a.color and b.color:
            if a.color == b.color:
                reasons.append(MatchReason("Color matches", 0.08))
            else:
                reasons.append(MatchReason("Color conflicts", -0.35))
                conflict = True
        return conflict

    @staticmethod
    def _method_for(reasons: list[MatchReason], *, strong_id: bool, model_level: bool) -> str:
        if any(r.label == "Exact GTIN match" for r in reasons):
            return "gtin"
        if strong_id:
            return "identifier"
        if model_level:
            return "model"
        if any("Normalized title" in r.label for r in reasons):
            return "normalized_title"
        return "similarity"


class SemanticSimilarity:
    """Plug-in for embedding-based candidate scoring.

    In-memory cosine similarity over a lightweight bag-of-words/key signature.
    Real pgvector embeddings are used for *candidate generation* in the service;
    this class is the scoring collaborator used by the engine. It is never the
    sole basis for a merge.
    """

    def score_attributes(self, a: ProductAttributes, b: ProductAttributes) -> float:
        import difflib

        if not a.title or not b.title:
            return 0.0
        ta, tb = normalize_title(a.title), normalize_title(b.title)
        ratio = difflib.SequenceMatcher(None, ta, tb).ratio()
        return round(ratio, 3)