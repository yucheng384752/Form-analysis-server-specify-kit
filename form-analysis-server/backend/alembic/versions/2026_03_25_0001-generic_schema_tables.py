"""Create generic schema tables: stations, station_schemas, station_links,
generic_records, generic_record_items, validation_rules, analytics_mappings.

Revision ID: 20260325_0001
Revises: 20260323_0004
Create Date: 2026-03-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260325_0001"
down_revision: Union[str, Sequence[str], None] = "20260323_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- stations --
    op.create_table(
        "stations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_items", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", "code", name="uq_stations_tenant_code"),
    )
    op.create_index("ix_stations_tenant_id", "stations", ["tenant_id"])

    # -- station_schemas --
    op.create_table(
        "station_schemas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("record_fields", postgresql.JSONB(), nullable=False),
        sa.Column("item_fields", postgresql.JSONB(), nullable=True),
        sa.Column("unique_key_fields", postgresql.JSONB(), nullable=False),
        sa.Column("csv_signature_columns", postgresql.JSONB(), nullable=True),
        sa.Column("csv_filename_pattern", sa.String(100), nullable=True),
        sa.Column("csv_field_mapping", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "station_id", "version", name="uq_station_schemas_version"
        ),
    )
    op.create_index("ix_station_schemas_station_id", "station_schemas", ["station_id"])

    # -- station_links --
    op.create_table(
        "station_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id"),
            nullable=False,
        ),
        sa.Column(
            "to_station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id"),
            nullable=False,
        ),
        sa.Column("link_type", sa.String(20), nullable=False),
        sa.Column(
            "link_config",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "tenant_id",
            "from_station_id",
            "to_station_id",
            name="uq_station_links_pair",
        ),
    )
    op.create_index("ix_station_links_tenant_id", "station_links", ["tenant_id"])

    # -- generic_records --
    op.create_table(
        "generic_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id"),
            nullable=False,
        ),
        sa.Column(
            "schema_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("station_schemas.id"),
            nullable=True,
        ),
        sa.Column("lot_no_raw", sa.String(50), nullable=False),
        sa.Column("lot_no_norm", sa.BigInteger(), nullable=False),
        sa.Column(
            "data", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_generic_records_tenant_station",
        "generic_records",
        ["tenant_id", "station_id"],
    )
    op.create_index(
        "ix_generic_records_lot_norm",
        "generic_records",
        ["tenant_id", "lot_no_norm"],
    )

    # -- generic_record_items --
    op.create_table(
        "generic_record_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generic_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column(
            "data", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("row_data", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "record_id", "row_no", name="uq_generic_items_record_row"
        ),
    )
    op.create_index(
        "ix_generic_items_record", "generic_record_items", ["record_id"]
    )
    op.create_index(
        "ix_generic_items_data",
        "generic_record_items",
        ["data"],
        postgresql_using="gin",
    )

    # -- validation_rules --
    op.create_table(
        "validation_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("rule_type", sa.String(30), nullable=False),
        sa.Column("rule_config", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.UniqueConstraint(
            "tenant_id",
            "station_id",
            "field_name",
            "rule_type",
            name="uq_validation_rules_field",
        ),
    )
    op.create_index(
        "ix_validation_rules_tenant_id", "validation_rules", ["tenant_id"]
    )

    # -- analytics_mappings --
    op.create_table(
        "analytics_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_path", sa.String(200), nullable=False),
        sa.Column("output_column", sa.String(100), nullable=False),
        sa.Column("output_order", sa.Integer(), nullable=False),
        sa.Column(
            "data_type", sa.String(20), nullable=False, server_default="'string'"
        ),
        sa.Column(
            "null_if_missing", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "station_id",
            "output_column",
            name="uq_analytics_mappings_col",
        ),
    )
    op.create_index(
        "ix_analytics_mappings_tenant_id", "analytics_mappings", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_table("analytics_mappings")
    op.drop_table("validation_rules")
    op.drop_table("generic_record_items")
    op.drop_table("generic_records")
    op.drop_table("station_links")
    op.drop_table("station_schemas")
    op.drop_table("stations")
