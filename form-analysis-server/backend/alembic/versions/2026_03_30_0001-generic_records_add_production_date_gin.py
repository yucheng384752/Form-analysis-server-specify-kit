"""Add production_date generated column and GIN index to generic_records.

Bug fixes:
  - Bug 1: generic_records missing production_date GENERATED ALWAYS AS stored column + index
            (date queries degraded to full table scan without it)
  - Bug 2: generic_records.data missing GIN index
            (JSONB containment queries degrade to full table scan without it)

Revision ID: 20260330_0001
Revises: 20260325_0001
Create Date: 2026-03-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260330_0001"
down_revision: Union[str, Sequence[str], None] = "20260325_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.columns"
            "  WHERE table_schema = 'public'"
            "    AND table_name = :table AND column_name = :column"
            ")"
        ),
        {"table": table, "column": column},
    )
    return bool(result.scalar())


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM pg_indexes"
            "  WHERE schemaname = 'public' AND indexname = :name"
            ")"
        ),
        {"name": name},
    )
    return bool(result.scalar())


def upgrade() -> None:
    # PostgreSQL requires GENERATED ALWAYS AS expressions to be IMMUTABLE.
    # Text->date cast is not considered immutable by default, so we first
    # create a helper function declared IMMUTABLE (safe for ISO-8601 strings).
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION _jsonb_text_to_date(j jsonb, k text)
            RETURNS date LANGUAGE sql IMMUTABLE CALLED ON NULL INPUT AS
            $$ SELECT CASE WHEN j->>k IS NOT NULL THEN (j->>k)::date END $$
            """
        )
    )

    # Bug 1: Add production_date GENERATED ALWAYS AS stored column
    if not _column_exists("generic_records", "production_date"):
        op.execute(
            sa.text(
                "ALTER TABLE generic_records "
                "ADD COLUMN production_date DATE "
                "GENERATED ALWAYS AS (_jsonb_text_to_date(data, 'production_date')) STORED"
            )
        )

    # Index on (tenant_id, production_date) for date-range queries
    if not _index_exists("ix_generic_records_prod_date"):
        op.execute(
            sa.text(
                "CREATE INDEX ix_generic_records_prod_date "
                "ON generic_records(tenant_id, production_date)"
            )
        )

    # Bug 2: Add GIN index on generic_records.data for JSONB containment queries
    # Note: use plain CREATE INDEX (not CONCURRENTLY) to stay inside transaction block.
    if not _index_exists("ix_generic_records_data_gin"):
        op.execute(
            sa.text(
                "CREATE INDEX ix_generic_records_data_gin "
                "ON generic_records USING GIN (data)"
            )
        )


def downgrade() -> None:
    if _index_exists("ix_generic_records_data_gin"):
        op.execute(sa.text("DROP INDEX IF EXISTS ix_generic_records_data_gin"))
    if _index_exists("ix_generic_records_prod_date"):
        op.execute(sa.text("DROP INDEX IF EXISTS ix_generic_records_prod_date"))
    if _column_exists("generic_records", "production_date"):
        op.execute(sa.text("ALTER TABLE generic_records DROP COLUMN production_date"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS _jsonb_text_to_date(jsonb, text)"))
