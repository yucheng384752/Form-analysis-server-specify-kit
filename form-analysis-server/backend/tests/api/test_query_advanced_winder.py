import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_db
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.models.p2_item_v2 import P2ItemV2
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
async def test_advanced_query_winder_does_not_include_p1(client, db_session):
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

    p1 = P1Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        extras={"rows": [{"Specification": "P1-SPEC"}]},
    )

    p2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        winder_number=5,
        extras={"rows": [{"format": "P2-FORMAT"}]},
    )
    p2.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=5,
            row_data={"format": "P2-FORMAT"},
        )
    ]

    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        production_date_yyyymmdd=20250101,
        machine_no="P24",
        mold_no="M1",
        product_id=None,
        extras={"rows": [{"specification": "P3-SPEC"}]},
    )
    p3.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_no,
            source_winder=5,
            specification="P3-SPEC",
            row_data={"source_winder": 5},
        )
    ]

    db_session.add_all([p1, p2, p3])
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={"lot_no": lot_no, "winder_number": "5"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    types = {r["data_type"] for r in payload["records"]}

    assert "P1" not in types
    assert "P2" in types
    assert "P3" in types


@pytest.mark.asyncio
async def test_advanced_query_invalid_winder_returns_400(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={"lot_no": "2507173_02", "winder_number": "abc"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
