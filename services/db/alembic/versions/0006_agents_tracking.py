"""create search_sessions, agent_runs, agent_events, watchlists, price_alerts, notifications, shopping_sessions

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

JSONB = postgresql.JSONB

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # search_sessions and agent_runs reference each other (session_id <-> run_id),
    # so one FK must be added after both tables exist (ALTER). This table is
    # created without the run_id FK first.
    op.create_table(
        "search_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("raw_query", sa.Text(), nullable=False),
        sa.Column("intent", JSONB(), nullable=True),
        sa.Column("currency_code", sa.CHAR(3), nullable=True),
        sa.Column("locale", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="completed"),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_summary", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_search_sessions_user_created", "search_sessions", ["user_id", "created_at"])

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("graph_name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_state", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["search_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_agent_runs_session", "agent_runs", ["session_id"])

    # Break the cycle: add run_id FK now that agent_runs exists.
    op.create_foreign_key(
        "fk_search_sessions_run_id",
        "search_sessions",
        "agent_runs",
        ["run_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "agent_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("agent", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("input_state", JSONB(), nullable=True),
        sa.Column("output_state", JSONB(), nullable=True),
        sa.Column("validation", JSONB(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_events_run_seq"),
    )

    op.create_table(
        "watchlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_watchlists_user_product"),
    )

    op.create_table(
        "price_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "kind",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("target_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("target_currency", sa.CHAR(3), nullable=True),
        sa.Column("percent_threshold", sa.Numeric(8, 4), nullable=True),
        sa.Column("triggering_offer", JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
    )
    op.create_check_constraint(
        "ck_price_alerts_kind",
        "price_alerts",
        "kind IN ('target_price','percent_drop','back_in_stock')",
    )
    op.create_check_constraint(
        "ck_price_alerts_status",
        "price_alerts",
        "status IN ('active','triggered','paused','cancelled')",
    )
    op.create_index("ix_price_alerts_status_kind", "price_alerts", ["status", "kind"])
    op.create_index("ix_price_alerts_product", "price_alerts", ["product_id"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False, server_default="in_app"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["alert_id"], ["price_alerts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_user_sent", "notifications", ["user_id", "sent_at"])

    op.create_table(
        "shopping_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intent_history", JSONB(), nullable=True),
        sa.Column("applied_filters", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("messages", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("prefs_snapshot", JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_shopping_sessions_user", "shopping_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_table("shopping_sessions")
    op.drop_table("notifications")
    op.drop_table("price_alerts")
    op.drop_table("watchlists")
    op.drop_table("agent_events")
    # break the search_sessions <-> agent_runs cycle BEFORE dropping either table
    op.drop_constraint("fk_search_sessions_run_id", "search_sessions", type_="foreignkey")
    # drop agent_runs first (it references search_sessions), then search_sessions
    op.drop_table("agent_runs")
    op.drop_table("search_sessions")