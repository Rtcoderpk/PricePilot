"""Product matching: normalization, identifiers, deterministic matching engine."""

from pricepilot.matching.engine import MatchingEngine, SemanticSimilarity  # noqa: F401
from pricepilot.matching.identifiers import ProductIdentifierSet, extract_identifiers  # noqa: F401
from pricepilot.normalization import (  # noqa: F401
    ProductAttributes,
    extract_color,
    normalize_brand,
    normalize_model,
    normalize_title,
    parse_quantity,
    parse_storage_gb,
)