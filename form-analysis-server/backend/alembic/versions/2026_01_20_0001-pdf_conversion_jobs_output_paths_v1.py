"""Add output_paths + ingested_upload_jobs to pdf_conversion_jobs

Revision ID: pdf_conv_jobs_outpaths_v1
Revises: tenant_api_keys_add_user_id_v1
Create Date: 2026-01-20 00:01:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "pdf_conv_jobs_outpaths_v1"
down_revision: Union[str, Sequence[str], None] = "tenant_api_keys_add_user_id_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("pdf_conversion_jobs"):
        return

    cols = {c["name"] for c in inspector.get_columns("pdf_conversion_jobs")}

    if "output_paths" not in cols:
        op.add_column(
            "pdf_conversion_jobs",
            sa.Column(
                "output_paths",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )
        # Best-effort backfill from legacy single-path column.
        op.execute(
            "UPDATE pdf_conversion_jobs "
            "SET output_paths = jsonb_build_array(output_path) "
            "WHERE output_path IS NOT NULL AND (output_paths IS NULL OR output_paths = 'null'::jsonb)"
        )

    if "ingested_upload_jobs" not in cols:
        op.add_column(
            "pdf_conversion_jobs",
            sa.Column(
                "ingested_upload_jobs",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("pdf_conversion_jobs"):
        return

    cols = {c["name"] for c in inspector.get_columns("pdf_conversion_jobs")}

    if "ingested_upload_jobs" in cols:
        op.drop_column("pdf_conversion_jobs", "ingested_upload_jobs")

    if "output_paths" in cols:
        op.drop_column("pdf_conversion_jobs", "output_paths")
