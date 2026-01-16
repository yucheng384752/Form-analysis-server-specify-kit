import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_db
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p2_item_v2 import P2ItemV2
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
async def test_v2_advanced_query_material_filters_p1_and_p2(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    lot_a = "2507173_02"
    lot_b = "2507173_03"

    p1_h2 = P1Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_a,
        lot_no_norm=normalize_lot_no(lot_a),
        extras={"material_code": "H2", "rows": [{"Specification": "P1-SPEC"}]},
    )
    p1_h5 = P1Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_b,
        lot_no_norm=normalize_lot_no(lot_b),
        extras={"material_code": "H5", "rows": [{"Specification": "P1-SPEC"}]},
    )

    p2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_a,
        lot_no_norm=normalize_lot_no(lot_a),
        winder_number=5,
        extras={},
    )
    p2.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=5,
            row_data={"material_code": "H2", "format": "P2-FORMAT"},
        )
    ]

    db_session.add_all([p1_h2, p1_h5, p2])
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={"material": "h2"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    types = {r["data_type"] for r in payload["records"]}
    assert "P1" in types
    assert "P2" in types

    for r in payload["records"]:
        if r["data_type"] == "P1":
            assert r["additional_data"].get("material_code") == "H2"
        if r["data_type"] == "P2":
            rows = (r.get("additional_data") or {}).get("rows") or []
            assert any((row.get("material_code") == "H2") for row in rows)


@pytest.mark.asyncio
async def test_v2_options_material_returns_constants(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get("/api/v2/query/options/material", headers=headers)
    assert resp.status_code == 200, resp.text
    materials = resp.json()

    assert "H2" in materials
