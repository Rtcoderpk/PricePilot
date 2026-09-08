"""Tests for the matching engine and normalization utilities."""

from __future__ import annotations

from pricepilot.matching.engine import MatchingEngine, SemanticSimilarity
from pricepilot.matching.identifiers import ProductIdentifierSet, extract_identifiers
from pricepilot.normalization import (
    ProductAttributes,
    extract_color,
    normalize_brand,
    normalize_model,
    normalize_title,
    parse_quantity,
    parse_storage_gb,
)


def norm_attrs(title, *, brand=None, model=None, storage=None, qty=None, color=None) -> ProductAttributes:
    return ProductAttributes(
        title=title,
        brand=brand,
        model=model,
        storage_gb=parse_storage_gb(storage) if storage else None,
        quantity=parse_quantity(qty) if qty else None,
        color=extract_color(color) if color else None,
    )


def idr(**kw) -> ProductIdentifierSet:
    return ProductIdentifierSet(**kw)


# ---------- normalization ----------

def test_normalize_title_different_formatting():
    a = normalize_title("Apple iPhone 17 Pro - 256 GB (Black)")
    b = normalize_title("Apple iPhone 17 Pro 256GB Black")
    # tokens sorted; stopwords removed; punctuation stripped; unit glued to digits
    assert a == b
    assert "256" in a and "black" in a and "gb" in a and "apple" in a


def test_normalize_title_decimals_and_units():
    assert normalize_title("Sidi Ali 1.5 L") == normalize_title("Sidi Ali 1.5L")


def test_normalize_title_drops_stopwords():
    assert "the" not in normalize_title("The Best Laptop New 2026")


def test_normalize_brand():
    assert normalize_brand("Apple Inc.") == "apple inc"
    assert normalize_brand(None) is None


def test_normalize_model():
    assert normalize_model("iPhone 17 Pro") == "iphone 17 pro"
    assert normalize_model(None) is None


def test_quantity_parsing():
    q1 = parse_quantity("1 kg")
    q2 = parse_quantity("1000 g")
    assert q1 is not None and q2 is not None
    assert q1.kind == q2.kind == "weight"
    assert abs(q1.value - q2.value) < 1e-6  # 1 kg == 1000 g


def test_quantity_variant_differs():
    q1 = parse_quantity("1 kg")
    q2 = parse_quantity("2 kg")
    assert abs(q1.value - q2.value) > 1


def test_quantity_volume_distinct_from_weight():
    q_w = parse_quantity("1 kg")
    q_v = parse_quantity("1 l")
    assert q_w.kind != q_v.kind


def test_storage_parse():
    assert parse_storage_gb("16GB RAM") == 16
    assert parse_storage_gb("1TB") == 1024
    assert parse_storage_gb("256GB") == 256
    assert parse_storage_gb(None) is None
    assert parse_storage_gb("cheap") is None


def test_color_extract():
    assert extract_color("iPhone 17 Pro 256GB Midnight") == "midnight"
    assert extract_color("black slate") == "black"
    assert extract_color("nice product") is None


# ---------- identifiers ----------

def test_extract_gtin_from_code():
    ids = extract_identifiers(raw={"code": "3017620422003"}, title="Nutella")
    assert ids.gtin == "3017620422003"
    assert ids.has_strong


def test_bad_id_rejected():
    ids = extract_identifiers(raw={"code": "not-a-gtin"}, title="x")
    assert ids.gtin is None


def test_mpn_extraction():
    ids = extract_identifiers(raw={"mpn": "AB-123"}, title="x")
    assert ids.mpn == "AB-123"


# ---------- matching ----------

def _mk(title, **kw) -> ProductAttributes:
    return norm_attrs(title, **kw)


def test_same_gtin_matches():
    e = MatchingEngine()
    a = _mk("Nutella", brand="Ferrero")
    b = _mk("Nutella 1kg", brand="Ferrero")
    r = e.match(a, b, a_id=idr(gtin="3017620422003"), b_id=idr(gtin="3017620422003"))
    assert r.matched is True
    assert r.confidence >= 0.98
    assert r.method == "gtin"


def test_different_gtin_does_not_match():
    e = MatchingEngine()
    a = _mk("Nutella", brand="Ferrero")
    b = _mk("Nutella", brand="Ferrero")
    r = e.match(a, b, a_id=idr(gtin="3017620422003"), b_id=idr(gtin="3017620422004"))
    assert r.hard_block is True
    assert r.matched is False
    assert r.method == "gtin_conflict"


def test_same_brand_model_matches():
    e = MatchingEngine()
    a = _mk("Apple iPhone 15 Pro 256GB", brand="Apple", model="iPhone 15 Pro", storage="256GB")
    b = _mk("iPhone 15 Pro 256GB", brand="Apple", model="iPhone 15 Pro", storage="256GB")
    r = e.match(a, b, a_id=idr(), b_id=idr())
    assert r.matched is True
    assert r.confidence >= 0.75
    assert r.method == "model"


def test_same_model_different_storage_is_variant():
    e = MatchingEngine()
    a = _mk("iPhone 15 Pro 128GB", brand="Apple", model="iPhone 15 Pro", storage="128GB")
    b = _mk("iPhone 15 Pro 256GB", brand="Apple", model="iPhone 15 Pro", storage="256GB")
    r = e.match(a, b, a_id=idr(), b_id=idr())
    assert r.hard_block is True
    assert r.matched is False
    assert r.method == "variant_conflict"


def test_different_brand_rejected():
    e = MatchingEngine()
    a = _mk("Galaxy S25", brand="Samsung", model="S25")
    b = _mk("Galaxy S25", brand="Apple", model="S25")
    r = e.match(a, b, a_id=idr(), b_id=idr())
    assert r.hard_block is True
    assert r.method == "brand_conflict"


def test_same_pack_vs_different_pack():
    e = MatchingEngine()
    a = _mk("Sidi Ali 1.5 L", brand="Sidi Ali", qty="1,5 L")
    b1 = _mk("Sidi Ali 1.5L", brand="Sidi Ali", qty="1500 ml")
    b2 = _mk("Sidi Ali 2 L", brand="Sidi Ali", qty="2 L")

    r_same = e.match(a, b1, a_id=idr(), b_id=idr())
    assert r_same.matched is True

    r_diff = e.match(a, b2, a_id=idr(), b_id=idr())
    assert r_diff.hard_block is True
    assert r_diff.matched is False


def test_semantic_support_not_sole_basis():
    e = MatchingEngine(semantic=SemanticSimilarity())
    # Identical title but no ids/brand/model → only title similarity
    a = _mk("Generic widget", brand=None, model=None)
    b = _mk("Generic widget", brand=None, model=None)
    r = e.match(a, b, a_id=idr(), b_id=idr())
    assert r.matched is True  # exact same normalized title is enough at 0.72


def test_conflicting_variant_beats_semantics():
    e = MatchingEngine(semantic=SemanticSimilarity())
    a = _mk("Samsung Galaxy S25 128GB", brand="Samsung", model="Galaxy S25", storage="128GB")
    b = _mk("Samsung Galaxy S25 512GB", brand="Samsung", model="Galaxy S25", storage="512GB")
    r = e.match(a, b, a_id=idr(), b_id=idr())
    # Very similar titles, same brand/model, same semantic — but storage differs
    assert r.hard_block is True
    assert r.matched is False
    assert r.confidence == 0.0