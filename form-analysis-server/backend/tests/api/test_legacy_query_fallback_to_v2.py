import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_db
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.p3_record import P3Record
from app.models.p3_item_v2 import P3ItemV2
from app.utils.normalization import normalize_lot_no


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_legacy_advanced_search_falls_back_to_v2_when_no_legacy_records(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    lot_no = "2507173_02"
    lot_no_norm = normalize_lot_no(lot_no)

    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        production_date_yyyymmdd=20250101,
        machine_no="P24",
        mold_no="M1",
        product_id="2025-01-01-P24-M1-2507173_02",
        extras={},
    )
    db_session.add(p3)
    await db_session.flush()  # ensure p3.id available

    item = P3ItemV2(
        tenant_id=tenant.id,
        p3_record_id=p3.id,
        row_no=1,
        lot_no=lot_no,
        source_winder=5,
        specification="P3-SPEC",
        row_data={"specification": "P3-SPEC", "source_winder": 5},
    )
    db_session.add(item)
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}

    # legacy endpoint should return v2-backed results when legacy tables are empty
    resp = await client.get(
        "/api/query/records/advanced",
        params={"lot_no": lot_no},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["total_count"] >= 1
    assert any(r["data_type"] == "P3" for r in payload["records"])

    p3_records = [r for r in payload["records"] if r["data_type"] == "P3"]
    assert p3_records
    assert p3_records[0].get("additional_data")
    assert p3_records[0]["additional_data"].get("rows"), payload


@pytest.mark.asyncio
async def test_legacy_advanced_search_winder_with_data_type_p1_does_not_return_p1(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    lot_no = "2507173_02"
    lot_no_norm = normalize_lot_no(lot_no)

    # Only v2 tables have data; legacy tables remain empty so legacy endpoint must fallback.
    p1 = P1Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        extras={"rows": [{"Specification": "P1-SPEC"}]},
    )
    db_session.add(p1)
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/query/records/advanced",
        params={"lot_no": lot_no, "winder_number": "5", "data_type": "P1"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_count"] == 0
    assert payload["records"] == []
