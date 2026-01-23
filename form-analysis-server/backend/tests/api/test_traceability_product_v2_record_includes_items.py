import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant
from app.models.p2_item_v2 import P2ItemV2
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.models.p3_item_v2 import P3ItemV2
from app.utils.normalization import normalize_lot_no


@pytest.fixture
async def client(db_session_clean):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


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
async def test_traceability_product_fallback_p3_record_includes_items_rows(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)

    # Use the canonical product_id format (underscore-delimited).
    product_id = "20250902_P24_238-2_301"
    lot_no_raw = "2507173_02"

    p3_record = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no_raw,
        lot_no_norm=normalize_lot_no(lot_no_raw),
        production_date_yyyymmdd=20250902,
        machine_no="P24",
        mold_no="238-2",
        product_id=product_id,
        extras={},
        created_at=datetime(2025, 9, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    db_session_clean.add(p3_record)
    await db_session_clean.flush()

    # Link an item (no matching product_id) so the endpoint must fall back to P3Record,
    # but still should include item rows via items_v2.
    db_session_clean.add(
        P3ItemV2(
            p3_record_id=p3_record.id,
            tenant_id=tenant.id,
            row_no=1,
            product_id=None,
            lot_no=lot_no_raw,
            production_date=date(2025, 9, 2),
            machine_no="P24",
            mold_no="238-2",
            production_lot=301,
            source_winder=5,
            specification="SPEC-A",
            row_data={"P3_No.": "2507173_02_05"},
        )
    )

    await db_session_clean.commit()

    resp = await client.get(
        f"/api/traceability/product/{product_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200

    data = resp.json()
    p3 = data.get("p3")
    assert isinstance(p3, dict)

    additional = p3.get("additional_data")
    assert isinstance(additional, dict)
    rows = additional.get("rows")
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].get("P3_No.") == "2507173_02_05"

    # Ensure source_winder can be derived even when record.extras is empty.
    assert p3.get("source_winder") == 5


@pytest.mark.asyncio
async def test_traceability_winder_p2_rows_present_even_when_row_data_missing(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)

    lot_no_raw = "2507173_02"
    winder_number = 7

    p2_record = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no_raw,
        lot_no_norm=normalize_lot_no(lot_no_raw),
        winder_number=winder_number,
        extras=None,
        created_at=datetime(2025, 9, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    db_session_clean.add(p2_record)
    await db_session_clean.flush()

    # Simulate datasets where row_data is None but structured fields exist.
    db_session_clean.add(
        P2ItemV2(
            p2_record_id=p2_record.id,
            tenant_id=tenant.id,
            winder_number=winder_number,
            row_data=None,
            sheet_width=150.0,
            thickness1=194.0,
            appearance=1,
        )
    )
    await db_session_clean.commit()

    resp = await client.get(
        f"/api/traceability/winder/{lot_no_raw}/{winder_number}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200

    data = resp.json()
    p2 = data.get("p2")
    assert isinstance(p2, dict)
    additional = p2.get("additional_data")
    assert isinstance(additional, dict)
    rows = additional.get("rows")
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert rows[0].get("winder_number") == winder_number
    assert rows[0].get("sheet_width") == 150.0
