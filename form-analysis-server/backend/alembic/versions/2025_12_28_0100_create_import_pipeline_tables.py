"""Create Import Pipeline Tables

Revision ID: import_pipeline_v2
Revises: refactor_v2
Create Date: 2025-12-28 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'import_pipeline_v2'
down_revision: Union[str, Sequence[str], None] = 'refactor_v2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Create import_jobs table
    if not inspector.has_table('import_jobs'):
        op.create_table('import_jobs',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('table_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('schema_version_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('batch_id', sa.String(length=100), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_files', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_rows', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('error_summary', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['schema_version_id'], ['schema_versions.id'], ),
            sa.ForeignKeyConstraint(['table_id'], ['table_registry.id'], ),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('batch_id')
        )

    # Create import_files table
    if not inspector.has_table('import_files'):
        op.create_table('import_files',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('table_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('file_hash', sa.String(length=64), nullable=False, comment='SHA-256'),
            sa.Column('storage_path', sa.String(length=512), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('row_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['job_id'], ['import_jobs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['table_id'], ['table_registry.id'], ),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

    # Create staging_rows table
    if not inspector.has_table('staging_rows'):
        op.create_table('staging_rows',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('row_index', sa.Integer(), nullable=False, comment='Original row number in file (1-based)'),
            sa.Column('parsed_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('errors_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
            sa.ForeignKeyConstraint(['file_id'], ['import_files.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['job_id'], ['import_jobs.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_staging_rows_is_valid'), 'staging_rows', ['is_valid'], unique=False)
        op.create_index(op.f('ix_staging_rows_job_id'), 'staging_rows', ['job_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_staging_rows_job_id'), table_name='staging_rows')
    op.drop_index(op.f('ix_staging_rows_is_valid'), table_name='staging_rows')
    op.drop_table('staging_rows')
    op.drop_table('import_files')
    op.drop_table('import_jobs')
