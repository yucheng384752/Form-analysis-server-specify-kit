"""Add slitting_result to p2_items_v2

Revision ID: 20260309_0003
Revises: 20260308_0002
Create Date: 2026-03-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260309_0003"
down_revision: Union[str, Sequence[str], None] = "20260308_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("p2_items_v2"):
        return

    cols = {c["name"] for c in inspector.get_columns("p2_items_v2")}
    if "slitting_result" not in cols:
        op.add_column(
            "p2_items_v2",
            sa.Column("slitting_result", sa.Integer(), nullable=True),
        )

    indexes = {ix["name"] for ix in inspector.get_indexes("p2_items_v2")}
    if "ix_p2_items_v2_tenant_slitting_result" not in indexes:
        op.create_index(
            "ix_p2_items_v2_tenant_slitting_result",
            "p2_items_v2",
            ["tenant_id", "slitting_result"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("p2_items_v2"):
        return

    indexes = {ix["name"] for ix in inspector.get_indexes("p2_items_v2")}
    if "ix_p2_items_v2_tenant_slitting_result" in indexes:
        op.drop_index(
            "ix_p2_items_v2_tenant_slitting_result",
            table_name="p2_items_v2",
        )

    cols = {c["name"] for c in inspector.get_columns("p2_items_v2")}
    if "slitting_result" in cols:
        op.drop_column("p2_items_v2", "slitting_result")
