"""Add winder_number to pdf_conversion_jobs

Revision ID: 20260323_0004
Revises: 20260309_0003
Create Date: 2026-03-23 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260323_0004"
down_revision: Union[str, Sequence[str], None] = "20260309_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("pdf_conversion_jobs"):
        return

    cols = {c["name"] for c in inspector.get_columns("pdf_conversion_jobs")}
    if "winder_number" not in cols:
        op.add_column(
            "pdf_conversion_jobs",
            sa.Column(
                "winder_number",
                sa.Integer(),
                nullable=True,
                comment="P2 winder number provided by user at conversion trigger time (1-20)",
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("pdf_conversion_jobs"):
        return

    cols = {c["name"] for c in inspector.get_columns("pdf_conversion_jobs")}
    if "winder_number" in cols:
        op.drop_column("pdf_conversion_jobs", "winder_number")
