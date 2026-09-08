"""add normalized attributes + variant key to products

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-08

Phase 2: a canonical product is a *variant-level* product that carries offers
from multiple merchant. `products` already plays that role. This migration adds
the normalized, variant-relevant attribute bag so the deterministic matcher can
be persisted and indexed without relying on free-text.

- `variant_key`: deterministic string identifying the exact variant
  (storage/quantity/color/...) so equality queries are indexable.
- `normalized_attrs`: structured JSON holding brand, model, storage_gb,
  quantity (kind+value+unit), color, condition, and per-field data-quality
  markers (verified | provider | inferred | missing).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

JSONB = postgresql.JSONB

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("variant_key", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("normalized_attrs", JSONB(), nullable=True))
    op.create_index("ix_products_variant_key", "products", ["variant_key"])
    op.create_index("ix_products_brand", "products", ["brand"])


def downgrade() -> None:
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_index("ix_products_variant_key", table_name="products")
    op.drop_column("products", "normalized_attrs")
    op.drop_column("products", "variant_key")