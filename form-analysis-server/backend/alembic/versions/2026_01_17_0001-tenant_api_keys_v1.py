"""Create tenant_api_keys table

Revision ID: tenant_api_keys_v1
Revises: import_pipeline_v2
Create Date: 2026-01-17 00:01:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "tenant_api_keys_v1"
down_revision: Union[str, Sequence[str], None] = "import_pipeline_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table("tenant_api_keys"):
        return

    op.create_table(
        "tenant_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False, server_default="default"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_tenant_api_keys_tenant_id_tenants"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_tenant_api_keys_key_hash"),
    )

    op.create_index("ix_tenant_api_keys_tenant_id", "tenant_api_keys", ["tenant_id"], unique=False)
    op.create_index("ix_tenant_api_keys_key_hash", "tenant_api_keys", ["key_hash"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("tenant_api_keys"):
        return

    op.drop_index("ix_tenant_api_keys_key_hash", table_name="tenant_api_keys")
    op.drop_index("ix_tenant_api_keys_tenant_id", table_name="tenant_api_keys")
    op.drop_table("tenant_api_keys")
