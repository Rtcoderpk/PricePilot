"""Canonical product construction from raw provider offers.

Pipeline: raw offers → per-offer attribute/identifier extraction → candidate
generation (deterministic + semantic) → pairwise matching → grouped canonical
products with offers.

Matching is deterministic and confidence-based (see `matching.engine`): strong
identifiers (barcode/GTIN) are decisive where present; variant signals
(storage/quantity/color) split products; semantic similarity is only a
supporting signal and never merges across a variant conflict.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pricepilot.logging import get_logger
from pricepilot.matching.engine import MatchingEngine, SemanticSimilarity
from pricepilot.matching.identifiers import ProductIdentifierSet, extract_identifiers
from pricepilot.normalization import (
    ProductAttributes,
    extract_color,
    normalize_brand,
    parse_quantity,
    parse_storage_gb,
)

if TYPE_CHECKING:
    from pricepilot.models import RawOffer

log = get_logger("services.canonical")


@dataclass
class CanonicalProduct:
    """A canonical product with one or more merchant offers."""

    product_id: str
    name: str
    brand: str | None = None
    category: str | None = None
    image_url: str | None = None
    variant: dict = field(default_factory=dict)
    match_confidence: float = 1.0
    match_method: str = "provider"
    offers: list[RawOffer] = field(default_factory=list)

    @property
    def best_price(self) -> float | None:
        priced = [o.price_amount for o in self.offers if o.price_amount is not None]
        return min(priced) if priced else None

    @property
    def provider_count(self) -> int:
        return len({o.data_source for o in self.offers})


@dataclass
class CandidateSignal:
    """Extracted signal for a single raw offer, ready for matching."""

    attributes: ProductAttributes
    identifiers: ProductIdentifierSet
    offer: RawOffer


def build_signals(offers: list[RawOffer]) -> list[CandidateSignal]:
    signals: list[CandidateSignal] = []
    for offer in offers:
        attrs = ProductAttributes(
            title=offer.title,
            brand=offer.brand,
            model=offer.model,
            quantity=parse_quantity(offer.quantity),
            storage_gb=parse_storage_gb(offer.storage or offer.title),
            color=extract_color(offer.title),
            condition=offer.raw.get("condition"),
        )
        ids = _identifiers_from_offer(offer, attrs)
        signals.append(CandidateSignal(attributes=attrs, identifiers=ids, offer=offer))
    return signals


def _identifiers_from_offer(offer: RawOffer, attrs: ProductAttributes):
    gtin = None
    mpn = None
    for ident in offer.identifiers:
        if ident.type in ("gtin", "ean", "upc") and not gtin:
            gtin = ident.value
        elif ident.type in ("mpn",) and not mpn:
            mpn = ident.value
    if not gtin:
        # fall back to raw dict keys if adapter didn't populate structured ids
        extracted = extract_identifiers(raw=offer.raw, title=offer.title, brand=offer.brand, model=offer.model)
        gtin = extracted.gtin
        mpn = mpn or extracted.mpn
    return ProductIdentifierSet(
        gtin=gtin,
        mpn=mpn,
        brand=normalize_brand(attrs.brand),
        model=attrs.model,
        title=attrs.title,
    )


def canonicalize(
    offers: list[RawOffer],
    *,
    engine: MatchingEngine | None = None,
    merge_threshold: float | None = None,
) -> list[CanonicalProduct]:
    """Group raw offers into canonical products using the matching engine.

    Grouping is O(n²) bounded by the candidate set size; the service caps
    candidates per provider so this stays cheap. Deterministic identifier
    lookup happens first (per-offer gtin), then pairwise matching for the rest.
    """
    sem = SemanticSimilarity()
    engine = engine or MatchingEngine(semantic=sem, merge_threshold=merge_threshold or 0.72)
    signals = build_signals(offers)
    return _cluster(signals, engine)


def _cluster(signals: list[CandidateSignal], engine: MatchingEngine) -> list[CanonicalProduct]:
    """Cluster signals into canonical products.

    Two-phase:
    1) Bucket by strong identifier (GTIN) when present — that's already a
       decisive identity, so no pairwise scoring is needed for those.
    2) For the remainder, greedily pairwise-match within the same brand/model
       candidate pool.
    """
    gtin_buckets: dict[str, list[CandidateSignal]] = {}
    others: list[CandidateSignal] = []
    for sig in signals:
        if sig.identifiers.gtin:
            gtin_buckets.setdefault(sig.identifiers.gtin, []).append(sig)
        else:
            others.append(sig)

    products: list[CanonicalProduct] = []
    for _gtin, bucket in gtin_buckets.items():
        products.append(_make_product(bucket, method="gtin", confidence=0.99))

    # pairwise clustering among un-matched signals
    clusters: list[list[CandidateSignal]] = []
    for sig in others:
        placed = False
        for cluster in clusters:
            representative = cluster[0]
            res = engine.match(
                sig.attributes,
                representative.attributes,
                a_id=sig.identifiers,
                b_id=representative.identifiers,
            )
            if res.matched and not res.hard_block:
                cluster.append(sig)
                placed = True
                _log_match(sig, representative, res)
                break
        if not placed:
            clusters.append([sig])

    for cluster in clusters:
        confidence = _cluster_confidence(cluster)
        method = cluster[0].identifiers.gtin and "gtin" or "attributes"
        products.append(_make_product(cluster, method=method, confidence=confidence))

    # Sort: products with a best price first, then by provider count.
    products.sort(key=lambda p: (p.best_price is None, p.provider_count), reverse=False)
    return products


def _cluster_confidence(cluster: list[CandidateSignal]) -> float:
    if len(cluster) == 1:
        return 1.0
    # average pairwise best confidence
    total, count = 0.0, 0
    representative = cluster[0]
    for sig in cluster[1:]:
        total += _pairwise_confidence(representative, sig)
        count += 1
    return round(total / count, 2) if count else 1.0


def _pairwise_confidence(a: CandidateSignal, b: CandidateSignal) -> float:
    from pricepilot.matching.engine import MatchingEngine, SemanticSimilarity

    return MatchingEngine(semantic=SemanticSimilarity()).match(
        a.attributes, b.attributes, a_id=a.identifiers, b_id=b.identifiers
    ).confidence


def _make_product(cluster: list[CandidateSignal], *, method: str, confidence: float) -> CanonicalProduct:
    ordered = sorted(cluster, key=lambda s: s.offer.price_amount is None or (s.offer.price_amount or 0))
    first = ordered[0]
    attrs = first.attributes
    offer = first.offer

    variant: dict = {}
    if attrs.storage_gb is not None:
        variant["storage_gb"] = attrs.storage_gb
    if attrs.quantity is not None:
        variant["quantity"] = f"{attrs.quantity.value:g}"
        variant["quantity_unit"] = attrs.quantity.unit
        variant["quantity_kind"] = attrs.quantity.kind
    if attrs.color:
        variant["color"] = attrs.color

    canonical_name = _name_for(attrs, offer)
    product_id = _product_id(first, method)

    return CanonicalProduct(
        product_id=product_id,
        name=canonical_name,
        brand=attrs.brand,
        category=offer.raw.get("categories"),
        image_url=offer.raw.get("image_small_url"),
        variant=variant,
        match_confidence=confidence,
        match_method=method,
        offers=[s.offer for s in ordered],
    )


def _name_for(attrs: ProductAttributes, offer: RawOffer) -> str:
    parts = [offer.title]
    if attrs.quantity is not None and attrs.quantity.raw not in offer.title:
        parts.append(f"({attrs.quantity.raw})")
    return " ".join(parts)


def _product_id(representative: CandidateSignal, method: str) -> str:
    if representative.identifiers.gtin:
        basis = f"gtin:{representative.identifiers.gtin}"
    else:
        basis = f"{representative.identifiers.brand or ''}:{representative.identifiers.model or ''}:{representative.attributes.variant_key or ''}"
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
    return f"pp_{method}_{digest}"


def _log_match(a: CandidateSignal, b: CandidateSignal, res) -> None:
    log.info(
        "product_match_decision matched=%s confidence=%s method=%s a=%s b=%s reasons=%s",
        res.matched,
        res.confidence,
        res.method,
        a.offer.title[:40],
        b.offer.title[:40],
        json.dumps(res.reasons, ensure_ascii=False),
    )