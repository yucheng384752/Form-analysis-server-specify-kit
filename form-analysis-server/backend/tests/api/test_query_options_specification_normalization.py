import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.api.deps import get_db
from app.main import app
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


@pytest.mark.asyncio
async def test_options_specification_deduplicates_pe32_variants(client, db_session):
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

    p3_a = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_a,
        lot_no_norm=normalize_lot_no(lot_a),
        production_date_yyyymmdd=20250101,
        machine_no="P24",
        mold_no="M1",
        product_id=None,
        extras={"rows": [{"specification": "PE 32"}]},
    )
    p3_a.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_a,
            source_winder=5,
            specification="PE 32",
            row_data={"specification": "PE 32"},
        )
    ]

    p3_b = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_b,
        lot_no_norm=normalize_lot_no(lot_b),
        production_date_yyyymmdd=20250102,
        machine_no="P24",
        mold_no="M1",
        product_id=None,
        extras={"rows": [{"specification": "PE32"}]},
    )
    p3_b.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_b,
            source_winder=5,
            specification="PE32",
            row_data={"specification": "PE32"},
        )
    ]

    db_session.add_all([p3_a, p3_b])
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get("/api/v2/query/options/specification", headers=headers)
    assert resp.status_code == 200, resp.text

    options = resp.json()

    # Must return a single merged option for the PE32 family.
    assert "PE 32" in options
    assert "PE32" not in options
