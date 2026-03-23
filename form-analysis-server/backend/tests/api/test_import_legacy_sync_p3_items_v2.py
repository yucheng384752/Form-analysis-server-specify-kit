import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.api.routes_import import _upsert_p3_record_for_analytics
from app.models.core.tenant import Tenant
from app.models.p3_item_v2 import P3ItemV2
from app.models.p3_record import P3Record
from app.utils.normalization import normalize_lot_no


async def _create_tenant(db_session_clean) -> Tenant:
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session_clean.add(tenant)
    await db_session_clean.commit()
    await db_session_clean.refresh(tenant)
    return tenant


@pytest.mark.asyncio
async def test_legacy_import_sync_upserts_p3_items_v2(db_session_clean):
    tenant = await _create_tenant(db_session_clean)

    lot_no_raw = "2507173_02"
    production_date = date(2025, 9, 2)

    first_row = {
        "Machine NO": "P24",
        "Mold NO": "238-2",
        "Specification": "SPEC-A",
        "Bottom Tape LOT": "BT-001",
        "lot": 301,
    }
    all_rows = [
        {
            **first_row,
            "Source Winder": 5,
            "P3_No.": "P3-001",
        },
        {
            **first_row,
            "Source Winder": 6,
            "P3_No.": "P3-002",
            "lot": 302,
        },
    ]

    await _upsert_p3_record_for_analytics(
        db=db_session_clean,
        tenant=tenant,
        lot_no_raw=lot_no_raw,
        production_date=production_date,
        first_row=first_row,
        all_rows=all_rows,
    )
    await db_session_clean.commit()

    # Confirm p3_records exists
    p3_record = (
        await db_session_clean.execute(
            select(P3Record).where(
                P3Record.tenant_id == tenant.id,
                P3Record.lot_no_norm == normalize_lot_no(lot_no_raw),
            )
        )
    ).scalar_one_or_none()
    assert p3_record is not None

    # Confirm p3_items_v2 are created and linked
    items = (
        (
            await db_session_clean.execute(
                select(P3ItemV2)
                .where(P3ItemV2.p3_record_id == p3_record.id)
                .order_by(P3ItemV2.row_no)
            )
        )
        .scalars()
        .all()
    )

    assert len(items) == 2
    assert items[0].row_no == 1
    # product_id is composed from production_date + machine_no + mold_no + lot
    assert items[0].product_id == "20250902_P24_238-2_301"
    assert items[0].source_winder == 5
    assert isinstance(items[0].row_data, dict)
    assert items[0].row_data.get("Mold NO") == "238-2"

    assert items[1].row_no == 2
    assert items[1].product_id == "20250902_P24_238-2_302"
    assert items[1].source_winder == 6
