"""Merge traceability heads

Revision ID: merge_traceability_heads_v1
Revises: trace_upload_jobs_last_status_v1, trace_import_jobs_last_status_v1
Create Date: 2026-01-17 00:02:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "merge_traceability_heads_v1"
down_revision: Union[str, Sequence[str], None] = (
    "trace_upload_jobs_last_status_v1",
    "trace_import_jobs_last_status_v1",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge-only revision: no schema changes.
    pass


def downgrade() -> None:
    # Merge-only revision: no schema changes.
    pass
