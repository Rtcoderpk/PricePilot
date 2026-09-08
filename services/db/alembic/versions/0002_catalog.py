"""create products, product_identifiers

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

JSONB = postgresql.JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=True, server_default=sa.text("'new'")),
        sa.Column("meta", JSONB(), nullable=True),
        sa.Column("is_fixture", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_products_canonical_name", "products", ["canonical_name"])

    op.create_table(
        "product_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "id_type",
            sa.Text(),
            nullable=False,
            server_default="sku",
        ),
        sa.Column("id_value", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("id_type", "id_value", name="uq_product_identifiers_type_value"),
    )
    op.create_check_constraint(
        "ck_product_identifiers_type",
        "product_identifiers",
        "id_type IN ('sku','gtin','upc','ean','mpn','model_number')",
    )
    op.create_index("ix_product_identifiers_product", "product_identifiers", ["product_id"])


def downgrade() -> None:
    op.drop_table("product_identifiers")
    op.drop_table("products")