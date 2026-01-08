"""Refactor Schema V2: Tenants, Registry, P1/P2/P3 Records

Revision ID: refactor_v2
Revises: 011dc47903ed
Create Date: 2025-12-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'refactor_v2'
down_revision: Union[str, Sequence[str], None] = '011dc47903ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Create tenants table
    if not inspector.has_table('tenants'):
        op.create_table('tenants',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('code', sa.String(length=50), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('is_default', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
            sa.UniqueConstraint('code'),
            comment='場域管理'
        )

    # 2. Create table_registry
    if not inspector.has_table('table_registry'):
        op.create_table('table_registry',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('table_code', sa.String(length=50), nullable=False),
            sa.Column('display_name', sa.String(length=100), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('table_code')
        )

    # 3. Create schema_versions
    if not inspector.has_table('schema_versions'):
        op.create_table('schema_versions',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('table_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('schema_hash', sa.String(length=64), nullable=False),
            sa.Column('header_fingerprint', sa.String(length=64), nullable=False),
            sa.Column('schema_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['table_id'], ['table_registry.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

    # 4. Create P1 Records
    if not inspector.has_table('p1_records'):
        op.create_table('p1_records',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('lot_no_raw', sa.String(length=50), nullable=False),
            sa.Column('lot_no_norm', sa.BigInteger(), nullable=False),
            sa.Column('schema_version_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('extras', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('tenant_id', 'lot_no_norm', name='uq_p1_tenant_lot_norm')
        )
        op.create_index('ix_p1_tenant_lot_norm', 'p1_records', ['tenant_id', 'lot_no_norm'], unique=False)

    # 5. Create P2 Records
    if not inspector.has_table('p2_records'):
        op.create_table('p2_records',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('lot_no_raw', sa.String(length=50), nullable=False),
            sa.Column('lot_no_norm', sa.BigInteger(), nullable=False),
            sa.Column('schema_version_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('extras', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
            sa.Column('winder_number', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('tenant_id', 'lot_no_norm', 'winder_number', name='uq_p2_tenant_lot_winder')
        )
        op.create_index('ix_p2_tenant_lot_norm', 'p2_records', ['tenant_id', 'lot_no_norm'], unique=False)

    # 6. Create P3 Records
    if not inspector.has_table('p3_records'):
        op.create_table('p3_records',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('lot_no_raw', sa.String(length=50), nullable=False),
            sa.Column('lot_no_norm', sa.BigInteger(), nullable=False),
            sa.Column('schema_version_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('extras', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
            sa.Column('production_date_yyyymmdd', sa.Integer(), nullable=False),
            sa.Column('machine_no', sa.String(length=20), nullable=False),
            sa.Column('mold_no', sa.String(length=50), nullable=False),
            sa.Column('product_id', sa.String(length=100), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('tenant_id', 'production_date_yyyymmdd', 'machine_no', 'mold_no', 'lot_no_norm', name='uq_p3_composite_key')
        )
        op.create_index('ix_p3_tenant_lot_norm', 'p3_records', ['tenant_id', 'lot_no_norm'], unique=False)
        op.create_index('ix_p3_tenant_prod_machine_mold', 'p3_records', ['tenant_id', 'production_date_yyyymmdd', 'machine_no', 'mold_no'], unique=False)
        op.create_index(op.f('ix_p3_records_product_id'), 'p3_records', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_p3_records_product_id'), table_name='p3_records')
    op.drop_index('ix_p3_tenant_prod_machine_mold', table_name='p3_records')
    op.drop_index('ix_p3_tenant_lot_norm', table_name='p3_records')
    op.drop_table('p3_records')
    
    op.drop_index('ix_p2_tenant_lot_norm', table_name='p2_records')
    op.drop_table('p2_records')
    
    op.drop_index('ix_p1_tenant_lot_norm', table_name='p1_records')
    op.drop_table('p1_records')
    
    op.drop_table('schema_versions')
    op.drop_table('table_registry')
    op.drop_table('tenants')
