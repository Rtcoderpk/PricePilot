"""phase 5: monitoring indexes + tracking/notification columns

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-08

Phase 5 (price monitoring) needs:
- `watchlists`: tracking fields (target_price, alert preferences, paused state,
  last monitoring status) on top of the existing user/product unique pairing.
- `price_alerts`: reused as-is; alerts reference it.
- `notifications`: an explicit `status` (unread/read/dismissed) and an index to
  prevent duplicate alerts per event via a unique event key on price_alerts.
- `prices`: an offer+poll-window index to prevent duplicate observations cheaply.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # watchlists: tracking metadata
    op.add_column("watchlists", sa.Column("target_price", sa.Numeric(14, 2), nullable=True))
    op.add_column("watchlists", sa.Column("target_currency", sa.CHAR(3), nullable=True))
    op.add_column(
        "watchlists",
        sa.Column(
            "alert_preferences",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("jsonb_build_object('price_drop', true, 'new_low', true, 'target_price', true)"),
        ),
    )
    op.add_column("watchlists", sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("watchlists", sa.Column("last_monitor_status", sa.Text(), nullable=True))
    op.add_column(
        "watchlists",
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # notifications: status lifecycle + read/unread
    op.add_column(
        "notifications",
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'unread'")),
    )
    op.create_check_constraint(
        "ck_notifications_status",
        "notifications",
        "status IN ('unread','read','dismissed')",
    )

    # price_alerts: unique event key for alert deduplication
    op.add_column("price_alerts", sa.Column("event_key", sa.Text(), nullable=True))
    op.create_index("ix_price_alerts_event_key", "price_alerts", ["event_key"], unique=True)

    # prices: index offer + poll window to cheaply dedupe observations
    op.create_index("ix_prices_offer_window", "prices", ["offer_id", "recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_prices_offer_window", table_name="prices")
    op.drop_index("ix_price_alerts_event_key", table_name="price_alerts")
    op.drop_column("price_alerts", "event_key")
    op.drop_constraint("ck_notifications_status", "notifications", type_="check")
    op.drop_column("notifications", "status")
    op.drop_column("watchlists", "last_observed_at")
    op.drop_column("watchlists", "last_monitor_status")
    op.drop_column("watchlists", "paused")
    op.drop_column("watchlists", "alert_preferences")
    op.drop_column("watchlists", "target_currency")
    op.drop_column("watchlists", "target_price")