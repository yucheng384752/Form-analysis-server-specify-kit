"""Add actor fields to import_jobs

Revision ID: trace_import_jobs_actor_v1
Revises: import_pipeline_v2
Create Date: 2026-01-16 00:02:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "trace_import_jobs_actor_v1"
down_revision: Union[str, Sequence[str], None] = "import_pipeline_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("import_jobs"):
        return

    cols = {c["name"] for c in inspector.get_columns("import_jobs")}

    if "actor_api_key_id" not in cols:
        op.add_column(
            "import_jobs",
            sa.Column("actor_api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index(
            op.f("ix_import_jobs_actor_api_key_id"),
            "import_jobs",
            ["actor_api_key_id"],
            unique=False,
        )
        op.create_foreign_key(
            "fk_import_jobs_actor_api_key_id_tenant_api_keys",
            "import_jobs",
            "tenant_api_keys",
            ["actor_api_key_id"],
            ["id"],
        )

    if "actor_label_snapshot" not in cols:
        op.add_column(
            "import_jobs",
            sa.Column("actor_label_snapshot", sa.String(length=100), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table("import_jobs"):
        return

    cols = {c["name"] for c in inspector.get_columns("import_jobs")}

    if "actor_label_snapshot" in cols:
        op.drop_column("import_jobs", "actor_label_snapshot")

    if "actor_api_key_id" in cols:
        try:
            op.drop_constraint("fk_import_jobs_actor_api_key_id_tenant_api_keys", "import_jobs", type_="foreignkey")
        except Exception:
            pass
        try:
            op.drop_index(op.f("ix_import_jobs_actor_api_key_id"), table_name="import_jobs")
        except Exception:
            pass
        op.drop_column("import_jobs", "actor_api_key_id")
