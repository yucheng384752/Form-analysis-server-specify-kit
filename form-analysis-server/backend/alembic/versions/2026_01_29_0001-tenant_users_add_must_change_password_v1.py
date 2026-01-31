"""Add must_change_password to tenant_users

Revision ID: 20260129_0001
Revises: pdf_conv_jobs_outpaths_v1
Create Date: 2026-01-29 00:01:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260129_0001"
down_revision: Union[str, Sequence[str], None] = "pdf_conv_jobs_outpaths_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("tenant_users"):
        return

    cols = {c["name"] for c in inspector.get_columns("tenant_users")}
    if "must_change_password" in cols:
        return

    op.add_column(
        "tenant_users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("tenant_users"):
        return

    cols = {c["name"] for c in inspector.get_columns("tenant_users")}
    if "must_change_password" not in cols:
        return

    op.drop_column("tenant_users", "must_change_password")
