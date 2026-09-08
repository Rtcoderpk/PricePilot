"""create merchants, sellers, product_offers

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

JSONB = postgresql.JSONB

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "merchants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("is_authoritative", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("domain", name="uq_merchants_domain"),
    )

    op.create_table(
        "sellers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("seller_ref", sa.Text(), nullable=True),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("return_policy", JSONB(), nullable=True),
        sa.Column("warranty", JSONB(), nullable=True),
        sa.Column("authenticity_flags", JSONB(), nullable=True),
        sa.Column(
            "confidence",
            sa.Text(),
            nullable=True,
            server_default="medium",
        ),
        sa.Column("data_source", sa.Text(), nullable=True),
        sa.Column("is_fixture", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("merchant_id", "seller_ref", name="uq_sellers_merchant_ref"),
    )
    op.create_index("ix_sellers_merchant", "sellers", ["merchant_id"])

    op.create_table(
        "product_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("price_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("price_currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("shipping_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("shipping_currency", sa.CHAR(3), nullable=True),
        sa.Column("tax_estimate", sa.Numeric(14, 2), nullable=True),
        sa.Column("fees", sa.Numeric(14, 2), nullable=True),
        sa.Column("coupon_discount", sa.Numeric(14, 2), nullable=True),
        sa.Column("coupon_code", sa.Text(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("data_source", sa.Text(), nullable=True),
        sa.Column("is_fixture", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.CheckConstraint("price_amount >= 0", name="ck_product_offers_price_nonneg"),
    )
    op.create_index("ix_product_offers_product_available", "product_offers", ["product_id", "available"])
    op.create_index("ix_product_offers_seller", "product_offers", ["seller_id"])
    op.create_index("ix_product_offers_price", "product_offers", ["price_amount"])


def downgrade() -> None:
    op.drop_table("product_offers")
    op.drop_table("sellers")
    op.drop_table("merchants")