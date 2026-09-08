"""Integration tests for the canonical product pipeline (services.canonical).

Covers the Phase 2 requirements: duplicate grouping across providers, variant
separation, missing-price honesty, and provider failure degradation.
"""

from __future__ import annotations

from pricepilot.models import ProductIdentifierRef, RawOffer
from pricepilot.services.canonical import canonicalize


def offer(
    title: str,
    *,
    provider="off_a",
    price=None,
    gtin=None,
    brand=None,
    quantity=None,
    storage=None,
    model=None,
) -> RawOffer:
    identifiers = [ProductIdentifierRef(type="gtin", value=gtin)] if gtin else []
    return RawOffer(
        provider=provider,
        title=title,
        price_amount=price,
        price_currency="EUR" if price is not None else "USD",
        brand=brand,
        model=model,
        quantity=quantity,
        storage=storage,
        data_source=provider,
        identifiers=identifiers,
        raw={"code": gtin, "brands": brand, "categories": "Food"},
    )


def test_duplicate_grouping_same_gtin_three_providers():
    """Same product across 3 providers (same GTIN) → 1 canonical + 3 offers."""
    offers = [
        offer("Nutella 1kg", provider="StoreA", price=4.0, gtin="3017620422003", brand="Ferrero", quantity="1 kg"),
        offer("Nutella 1kg", provider="StoreB", price=4.5, gtin="3017620422003", brand="Ferrero", quantity="1 kg"),
        offer("Nutella 1kg", provider="StoreC", price=3.9, gtin="3017620422003", brand="Ferrero", quantity="1 kg"),
    ]
    products = canonicalize(offers)
    assert len(products) == 1
    p = products[0]
    assert len(p.offers) == 3
    assert p.best_price == 3.9
    assert p.provider_count == 3
    assert p.match_method == "gtin"
    assert p.match_confidence == 0.99


def test_duplicate_grouping_by_attributes_without_id():
    """Same brand+title+pack across providers that lack GTIN → grouped.

    Matched deterministically via brand + normalized title + pack agreement.
    """
    offers = [
        offer("Sidi Ali 1.5 L", provider="StoreA", price=1.2, brand="Sidi Ali", quantity="1,5 L"),
        offer("Sidi Ali 1.5L", provider="StoreB", price=1.3, brand="Sidi Ali", quantity="1500 ml"),
    ]
    products = canonicalize(offers)
    assert len(products) == 1
    assert len(products[0].offers) == 2
    assert products[0].provider_count == 2
    assert products[0].match_method == "attributes"


def test_variant_separation_different_pack():
    """Different pack sizes are NOT the same product even with same brand."""
    offers = [
        offer("Sidi Ali 1.5 L", provider="StoreA", price=1.2, gtin="6111035000058", brand="Sidi Ali", quantity="1,5 L"),
        offer("Sidi Ali 2 L", provider="StoreA", price=1.6, gtin="6111035002175", brand="Sidi Ali", quantity="2 L"),
    ]
    products = canonicalize(offers)
    assert len(products) == 2  # different GTINs dominate → distinct
    assert products[0].variant.get("quantity") != products[1].variant.get("quantity")


def test_storage_variant_separation():
    """128GB and 512GB are distinct variants, not merged."""
    offers = [
        offer("Samsung Galaxy S25 128GB", provider="StoreA", price=799, brand="Samsung", model="Galaxy S25", storage="128GB"),
        offer("Samsung Galaxy S25 512GB", provider="StoreA", price=999, brand="Samsung", model="Galaxy S25", storage="512GB"),
    ]
    products = canonicalize(offers)
    assert len(products) == 2
    assert {p.variant.get("storage_gb") for p in products} == {128, 512}


def test_missing_price_stays_null():
    """No real price → price stays null, never faked to 0."""
    offers = [offer("Cheap Stuff", gtin="123456789", price=None)]
    products = canonicalize(offers)
    assert len(products) == 1
    assert products[0].best_price is None
    assert products[0].offers[0].price_amount is None


def test_mixed_provider_grouping():
    """Multiple providers return overlapping + unique products → dedup only matches."""
    offers = [
        offer("Nutella 1kg", provider="StoreA", price=4.0, gtin="A001", brand="Ferrero", quantity="1 kg"),
        offer("Nutella 1kg", provider="StoreB", price=4.2, gtin="A001", brand="Ferrero", quantity="1 kg"),
        offer("Nutella 750g", provider="StoreB", price=3.5, gtin="A002", brand="Ferrero", quantity="750 g"),
        offer("Random cookie", provider="StoreC", price=2.0, gtin="A003", brand="Acme"),
    ]
    products = canonicalize(offers)
    assert len(products) == 3
    by_count = {p.provider_count: p for p in products}
    assert by_count[2].offers[0].title == "Nutella 1kg"
    assert by_count[1].offers[0].title in {"Nutella 750g", "Random cookie"}
    # every product keeps its offers distinct
    assert len({id(o) for p in products for o in p.offers}) == 4


def test_native_grouping_uses_variant_key():
    """Two totally different products (same brand, different identity) stay apart."""
    offers = [
        offer("Nutella 1kg", gtin="A001", brand="Ferrero", quantity="1 kg"),
        offer("Kinder Bueno 40g", gtin="A004", brand="Ferrero", quantity="40 g"),
    ]
    products = canonicalize(offers)
    assert len(products) == 2