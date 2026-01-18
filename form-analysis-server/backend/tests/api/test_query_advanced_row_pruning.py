import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant
from app.models.p2_record import P2Record
from app.models.p2_item_v2 import P2ItemV2
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


async def _create_tenant(db_session) -> Tenant:
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.mark.asyncio
async def test_v2_advanced_prunes_p2_rows_to_matching_specification(client, db_session):
    tenant = await _create_tenant(db_session)

    lot = "2507173_02"
    p2_match = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=normalize_lot_no(lot),
        winder_number=5,
        extras={},
    )
    p2_match.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=5,
            row_data={"format": "PE 32", "winder_number": 5},
        )
    ]

    p2_other = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=normalize_lot_no(lot),
        winder_number=7,
        extras={},
    )
    p2_other.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=7,
            row_data={"format": "PP 33", "winder_number": 7},
        )
    ]

    db_session.add_all([p2_match, p2_other])
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={"lot_no": lot, "data_type": "P2", "specification": "PE32"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] == 1
    rec = payload["records"][0]
    rows = (rec.get("additional_data") or {}).get("rows")
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].get("winder_number") == 5
    assert "PE" in str(rows[0].get("format", ""))


@pytest.mark.asyncio
async def test_v2_advanced_prunes_p3_rows_to_matching_specification(client, db_session):
    tenant = await _create_tenant(db_session)

    lot = "2507173_03"
    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=normalize_lot_no(lot),
        production_date_yyyymmdd=20250101,
        machine_no="P24",
        mold_no="M1",
        product_id=None,
        extras={"rows": [{"specification": "PE 32"}]},
    )
    p3.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot,
            source_winder=5,
            specification="PE 32",
            row_data={"specification": "PE 32", "source_winder": 5},
        ),
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=2,
            lot_no=lot,
            source_winder=6,
            specification="PP 33",
            row_data={"specification": "PP 33", "source_winder": 6},
        ),
    ]

    db_session.add(p3)
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={"lot_no": lot, "data_type": "P3", "specification": "PE32"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] == 1
    rec = payload["records"][0]
    rows = (rec.get("additional_data") or {}).get("rows")
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert (rows[0].get("specification") or "").replace(" ", "").upper().startswith("PE")
