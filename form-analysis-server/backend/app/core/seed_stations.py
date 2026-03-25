"""Seed default station definitions for existing manufacturing tenants."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.core.tenant import Tenant
from app.models.station import Station, StationLink, StationSchema

# Station definitions for the current manufacturing domain.
# These will be inserted once per tenant when USE_GENERIC_SCHEMA is enabled.
_STATION_DEFS = [
    {"code": "P1", "name": "押出/成型", "sort_order": 1, "has_items": False},
    {"code": "P2", "name": "分條", "sort_order": 2, "has_items": True},
    {"code": "P3", "name": "沖切/分離", "sort_order": 3, "has_items": True},
]

_P1_RECORD_FIELDS = [
    {
        "name": "product_name",
        "type": "string",
        "required": False,
        "label": {"zh-TW": "產品名稱", "en": "Product Name"},
    },
    {
        "name": "material_code",
        "type": "string",
        "required": False,
        "label": {"zh-TW": "材料代碼", "en": "Material Code"},
        "filterable": True,
    },
    {
        "name": "quantity",
        "type": "integer",
        "required": False,
        "label": {"zh-TW": "數量", "en": "Quantity"},
    },
    {
        "name": "production_date",
        "type": "date",
        "required": False,
        "label": {"zh-TW": "生產日期", "en": "Production Date"},
    },
]

_P2_RECORD_FIELDS = [
    {
        "name": "winder_number",
        "type": "integer",
        "required": True,
        "label": {"zh-TW": "捲收機號", "en": "Winder Number"},
        "indexed": True,
        "filterable": True,
        "min": 1,
        "max": 20,
    },
]

_P2_ITEM_FIELDS = [
    {
        "name": "winder_number",
        "type": "integer",
        "required": True,
        "label": {"zh-TW": "捲收機號", "en": "Winder Number"},
    },
    {
        "name": "sheet_width",
        "type": "float",
        "required": False,
        "label": {"zh-TW": "半成品寬度(mm)", "en": "Sheet Width(mm)"},
        "unit": "mm",
    },
    {
        "name": "thickness1",
        "type": "float",
        "required": False,
        "label": {"zh-TW": "厚度1", "en": "Thickness 1"},
    },
    {
        "name": "thickness2",
        "type": "float",
        "required": False,
        "label": {"zh-TW": "厚度2", "en": "Thickness 2"},
    },
    {
        "name": "thickness3",
        "type": "float",
        "required": False,
        "label": {"zh-TW": "厚度3", "en": "Thickness 3"},
    },
    {
        "name": "thickness4",
        "type": "float",
        "required": False,
        "label": {"zh-TW": "厚度4", "en": "Thickness 4"},
    },
    {
        "name": "thickness5",
        "type": "float",
        "required": False,
        "label": {"zh-TW": "厚度5", "en": "Thickness 5"},
    },
    {
        "name": "thickness6",
        "type": "float",
        "required": False,
        "label": {"zh-TW": "厚度6", "en": "Thickness 6"},
    },
    {
        "name": "thickness7",
        "type": "float",
        "required": False,
        "label": {"zh-TW": "厚度7", "en": "Thickness 7"},
    },
    {
        "name": "appearance",
        "type": "integer",
        "required": False,
        "label": {"zh-TW": "外觀", "en": "Appearance"},
    },
    {
        "name": "rough_edge",
        "type": "integer",
        "required": False,
        "label": {"zh-TW": "毛邊", "en": "Rough Edge"},
    },
    {
        "name": "slitting_result",
        "type": "integer",
        "required": False,
        "label": {"zh-TW": "分條結果", "en": "Slitting Result"},
    },
]

_P3_RECORD_FIELDS = [
    {
        "name": "production_date_yyyymmdd",
        "type": "integer",
        "required": True,
        "label": {"zh-TW": "生產日期(YYYYMMDD)", "en": "Production Date (YYYYMMDD)"},
    },
    {
        "name": "machine_no",
        "type": "string",
        "required": True,
        "label": {"zh-TW": "機台編號", "en": "Machine No"},
        "filterable": True,
    },
    {
        "name": "mold_no",
        "type": "string",
        "required": True,
        "label": {"zh-TW": "模具編號", "en": "Mold No"},
        "filterable": True,
    },
    {
        "name": "product_id",
        "type": "string",
        "required": False,
        "label": {"zh-TW": "產品ID", "en": "Product ID"},
        "indexed": True,
    },
]

_P3_ITEM_FIELDS = [
    {
        "name": "product_id",
        "type": "string",
        "required": False,
        "label": {"zh-TW": "產品ID", "en": "Product ID"},
    },
    {
        "name": "lot_no",
        "type": "string",
        "required": True,
        "label": {"zh-TW": "批號", "en": "Lot No"},
    },
    {
        "name": "production_date",
        "type": "date",
        "required": False,
        "label": {"zh-TW": "生產日期", "en": "Production Date"},
    },
    {
        "name": "machine_no",
        "type": "string",
        "required": False,
        "label": {"zh-TW": "機台編號", "en": "Machine No"},
    },
    {
        "name": "mold_no",
        "type": "string",
        "required": False,
        "label": {"zh-TW": "模具編號", "en": "Mold No"},
    },
    {
        "name": "production_lot",
        "type": "integer",
        "required": False,
        "label": {"zh-TW": "生產序號", "en": "Production Lot"},
    },
    {
        "name": "source_winder",
        "type": "integer",
        "required": False,
        "label": {"zh-TW": "來源分條", "en": "Source Winder"},
        "filterable": True,
    },
    {
        "name": "specification",
        "type": "string",
        "required": False,
        "label": {"zh-TW": "規格", "en": "Specification"},
    },
    {
        "name": "bottom_tape_lot",
        "type": "string",
        "required": False,
        "label": {"zh-TW": "底帶批號", "en": "Bottom Tape Lot"},
    },
]

_SCHEMA_MAP = {
    "P1": {
        "record_fields": _P1_RECORD_FIELDS,
        "item_fields": None,
        "unique_key_fields": ["lot_no_norm"],
        "csv_filename_pattern": "P1_*",
    },
    "P2": {
        "record_fields": _P2_RECORD_FIELDS,
        "item_fields": _P2_ITEM_FIELDS,
        "unique_key_fields": ["lot_no_norm", "winder_number"],
        "csv_filename_pattern": "P2_*",
    },
    "P3": {
        "record_fields": _P3_RECORD_FIELDS,
        "item_fields": _P3_ITEM_FIELDS,
        "unique_key_fields": [
            "lot_no_norm",
            "production_date_yyyymmdd",
            "machine_no",
            "mold_no",
        ],
        "csv_filename_pattern": "P3_*",
    },
}

_LINK_DEFS = [
    {
        "from_code": "P3",
        "to_code": "P2",
        "link_type": "lot_no",
        "link_config": {
            "from_field": "data.source_winder",
            "to_field": "data.winder_number",
            "shared_key": "lot_no_norm",
            "description": "P3 traces back to P2 via lot_no + winder",
        },
        "sort_order": 1,
    },
    {
        "from_code": "P2",
        "to_code": "P1",
        "link_type": "lot_no",
        "link_config": {
            "shared_key": "lot_no_norm",
            "description": "P2 traces back to P1 via lot_no",
        },
        "sort_order": 2,
    },
]


async def seed_stations(session_factory: async_sessionmaker) -> None:
    """Ensure every active tenant has P1/P2/P3 station definitions.

    Idempotent — skips tenants that already have stations.
    """
    async with session_factory() as db:
        tenants = (
            (await db.execute(select(Tenant).where(Tenant.is_active == True)))
            .scalars()
            .all()
        )

        for tenant in tenants:
            existing_codes = set(
                (
                    await db.execute(
                        select(Station.code).where(Station.tenant_id == tenant.id)
                    )
                )
                .scalars()
                .all()
            )

            if existing_codes:
                continue

            station_map: dict[str, Station] = {}
            for sdef in _STATION_DEFS:
                station = Station(tenant_id=tenant.id, **sdef)
                db.add(station)
                station_map[sdef["code"]] = station

            await db.flush()

            for code, station in station_map.items():
                schema_def = _SCHEMA_MAP[code]
                db.add(
                    StationSchema(
                        station_id=station.id,
                        version=1,
                        is_active=True,
                        record_fields=schema_def["record_fields"],
                        item_fields=schema_def["item_fields"],
                        unique_key_fields=schema_def["unique_key_fields"],
                        csv_filename_pattern=schema_def["csv_filename_pattern"],
                    )
                )

            for ldef in _LINK_DEFS:
                from_station = station_map[ldef["from_code"]]
                to_station = station_map[ldef["to_code"]]
                db.add(
                    StationLink(
                        tenant_id=tenant.id,
                        from_station_id=from_station.id,
                        to_station_id=to_station.id,
                        link_type=ldef["link_type"],
                        link_config=ldef["link_config"],
                        sort_order=ldef["sort_order"],
                    )
                )

        await db.commit()
