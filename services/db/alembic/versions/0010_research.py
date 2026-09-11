"""research_runs — supplier product research persistence (Phase flagship flow)

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-11

Stores a normalized product query + the full retrieved supplier research so the
UI can show history. We intentionally store the query and result JSONB rather
than image binaries — images stay on the client/object storage.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("input_type", sa.Text(), nullable=False, server_default="text"),  # text|voice|image
        sa.Column("original_request", sa.Text(), nullable=True),
        sa.Column("product_query", postgresql.JSONB(), nullable=True),
        sa.Column("results", postgresql.JSONB(), nullable=True),  # supplier results + comparison
        sa.Column("recommendation", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="completed"),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_research_runs_user_created", "research_runs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_research_runs_user_created", table_name="research_runs")
    op.drop_table("research_runs")