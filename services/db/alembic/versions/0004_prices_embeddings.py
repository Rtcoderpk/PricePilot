"""create prices, product_embeddings

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("source", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["offer_id"], ["product_offers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.CheckConstraint("amount >= 0", name="ck_prices_amount_nonneg"),
    )
    op.create_index("ix_prices_product_recorded", "prices", ["product_id", "recorded_at"])

    # pgvector extension + embedding column (1536-dim OpenAI-compatible).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "CREATE TABLE product_embeddings ("
        "  product_id UUID PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,"
        "  embedding vector(1536) NOT NULL,"
        "  model TEXT NOT NULL,"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )
    op.execute("CREATE INDEX ix_product_embeddings_vec ON product_embeddings USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.drop_table("product_embeddings")
    op.drop_table("prices")