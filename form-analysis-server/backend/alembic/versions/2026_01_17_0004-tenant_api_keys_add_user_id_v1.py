"""Add user_id to tenant_api_keys

Revision ID: tenant_api_keys_add_user_id_v1
Revises: tenant_users_v1
Create Date: 2026-01-17 00:04:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "tenant_api_keys_add_user_id_v1"
down_revision: Union[str, Sequence[str], None] = "tenant_users_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("tenant_api_keys"):
        return

    cols = {c["name"] for c in inspector.get_columns("tenant_api_keys")}

    if "user_id" not in cols:
        op.add_column(
            "tenant_api_keys",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index(
            "ix_tenant_api_keys_user_id",
            "tenant_api_keys",
            ["user_id"],
            unique=False,
        )
        op.create_foreign_key(
            "fk_tenant_api_keys_user_id_tenant_users",
            "tenant_api_keys",
            "tenant_users",
            ["user_id"],
            ["id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("tenant_api_keys"):
        return

    cols = {c["name"] for c in inspector.get_columns("tenant_api_keys")}
    if "user_id" not in cols:
        return

    op.drop_constraint("fk_tenant_api_keys_user_id_tenant_users", "tenant_api_keys", type_="foreignkey")
    op.drop_index("ix_tenant_api_keys_user_id", table_name="tenant_api_keys")
    op.drop_column("tenant_api_keys", "user_id")
