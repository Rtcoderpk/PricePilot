"""Enable RLS and (when Supabase roles exist) add policies

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-08

Local dev Postgres has no `anon` / `authenticated` / `service_role` roles, so
RLS is enabled (harmless there) and policies are created only when the Supabase
roles exist. This keeps one schema portable to both targets without breaking
`docker compose` bring-up.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that carry per-user data → enable RLS everywhere.
OWNER_TABLES = [
    "profiles",
    "user_preferences",
    "watchlists",
    "price_alerts",
    "notifications",
    "search_sessions",
    "shopping_sessions",
]
# Public read catalog → RLS to `anon`.
PUBLIC_READ_TABLES = [
    "products",
    "product_identifiers",
    "merchants",
    "sellers",
    "product_offers",
    "prices",
    "reviews",
    "review_summaries",
    "product_embeddings",
    "agent_runs",
    "agent_events",
]

_POLICY_SQL = """
DO $rls$
BEGIN
  -- only run when targeting Supabase (roles exist); local docker has none
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated')
     AND EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN

    ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;

    CREATE POLICY {policy_name} ON public.{table}
      FOR {command}
      TO {roles}
      USING ({using});
  END IF;
END
$rls$;
"""


def upgrade() -> None:
    for table in OWNER_TABLES + PUBLIC_READ_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")

    for table in OWNER_TABLES:
        # owner-scoped (user_id column) select/insert/update/delete
        op.execute(
            _POLICY_SQL.format(
                table=table,
                policy_name=f"rls_{table}_user_all",
                command="ALL",
                roles="authenticated",
                using=f"user_id = (select auth.uid()::uuid)",
            )
        )

    for table in PUBLIC_READ_TABLES:
        op.execute(
            _POLICY_SQL.format(
                table=table,
                policy_name=f"rls_{table}_anon_read",
                command="SELECT",
                roles="anon, authenticated",
                using="true",
            )
        )


def downgrade() -> None:
    for table in OWNER_TABLES + PUBLIC_READ_TABLES:
        op.execute(
            f"DROP POLICY IF EXISTS rls_{table}_user_all ON public.{table};"
            if table in OWNER_TABLES
            else f"DROP POLICY IF EXISTS rls_{table}_anon_read ON public.{table};"
        )
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY;")