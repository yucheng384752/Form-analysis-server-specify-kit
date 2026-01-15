import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_db
from app.models.core.tenant import Tenant
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


async def _seed_tenant_with_p3(db_session) -> tuple[Tenant, str]:
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

    return tenant, lot_no


@pytest.mark.asyncio
async def test_legacy_records_falls_back_to_v2_when_no_legacy_records(client, db_session):
    tenant, lot_no = await _seed_tenant_with_p3(db_session)

    resp = await client.get(
        "/api/query/records",
        params={"lot_no": lot_no, "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["total_count"] >= 1
    assert any(r["data_type"] == "P3" for r in payload["records"])


@pytest.mark.asyncio
async def test_legacy_lot_suggestions_falls_back_to_v2_when_no_legacy_records(client, db_session):
    tenant, lot_no = await _seed_tenant_with_p3(db_session)

    resp = await client.get(
        "/api/query/lots/suggestions",
        params={"query": "2507", "limit": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    suggestions = resp.json()
    assert isinstance(suggestions, list)
    assert lot_no in suggestions


@pytest.mark.asyncio
async def test_legacy_field_options_falls_back_to_v2_when_no_legacy_records(client, db_session):
    tenant, _ = await _seed_tenant_with_p3(db_session)

    resp = await client.get(
        "/api/query/options/machine_no",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    options = resp.json()
    assert isinstance(options, list)
    assert "P24" in options
