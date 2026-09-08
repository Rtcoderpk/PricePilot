"""create users, profiles, user_preferences

Revision ID: 0001
Revises:
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

JSONB = postgresql.JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.dialects.postgresql.CITEXT(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_profiles_user_id"),
    )

    op.create_table(
        "user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preferred_brands", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("max_budget", sa.Numeric(14, 2), nullable=True),
        sa.Column("min_specs", JSONB(), nullable=True),
        sa.Column("preferred_stores", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column(
            "preferred_condition",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
            server_default=sa.text("ARRAY['new','refurbished','any']::text[]"),
        ),
        sa.Column(
            "price_vs_quality",
            sa.Numeric(3, 2),
            nullable=True,
            # note: check constraint added below with a name
        ),
        sa.Column(
            "currency_code",
            sa.CHAR(3),
            nullable=True,
            server_default=sa.text("'USD'"),
        ),
        sa.Column("shopping_locale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )
    op.create_check_constraint(
        "ck_user_preferences_condition",
        "user_preferences",
        "preferred_condition <@ ARRAY['new','refurbished','any']::text[]",
    )
    op.create_check_constraint(
        "ck_user_preferences_price_vs_quality",
        "user_preferences",
        "price_vs_quality >= 0 AND price_vs_quality <= 1",
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_table("profiles")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS citext")