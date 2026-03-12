import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant
from app.models.p3_item_v2 import P3ItemV2
from app.models.p3_record import P3Record
from app.utils.normalization import normalize_lot_no


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
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
async def test_v2_advanced_query_normalizes_specification_ascii_and_fullwidth(
    client, db_session
):
    tenant = await _create_tenant(db_session)

    lot_ascii = "2507173_02"
    lot_fullwidth = "2507173_03"

    p3_ascii = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_ascii,
        lot_no_norm=normalize_lot_no(lot_ascii),
        production_date_yyyymmdd=20250101,
        machine_no="P24",
        mold_no="M1",
        product_id=f"2025-01-01-P24-M1-{lot_ascii}",
        extras={"rows": [{"specification": "PE 32"}]},
        created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    p3_ascii.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_ascii,
            source_winder=5,
            specification="PE 32",
            row_data={"specification": "PE 32", "source_winder": 5},
        )
    ]

    p3_fullwidth = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_fullwidth,
        lot_no_norm=normalize_lot_no(lot_fullwidth),
        production_date_yyyymmdd=20250102,
        machine_no="P24",
        mold_no="M1",
        product_id=f"2025-01-02-P24-M1-{lot_fullwidth}",
        extras={"rows": [{"specification": "ＰＥ３２"}]},
        created_at=datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    p3_fullwidth.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_fullwidth,
            source_winder=5,
            specification="ＰＥ３２",
            row_data={"specification": "ＰＥ３２", "source_winder": 5},
        )
    ]

    db_session.add_all([p3_ascii, p3_fullwidth])
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={"specification": "PE32"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    lots = {r["lot_no"] for r in payload["records"]}
    assert lot_ascii in lots
    assert lot_fullwidth in lots


@pytest.mark.asyncio
async def test_v2_advanced_query_normalizes_machine_and_product_id(client, db_session):
    tenant = await _create_tenant(db_session)

    lot = "1234567_01"
    lot_norm = normalize_lot_no(lot)
    product_id = "2025-01-03-P24-M1-1234567_01"

    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=lot_norm,
        production_date_yyyymmdd=20250103,
        machine_no="P24",
        mold_no="M1",
        product_id=product_id,
        extras={"rows": [{"specification": "PE 32"}]},
    )
    p3.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot,
            source_winder=5,
            specification="PE 32",
            row_data={
                "specification": "PE 32",
                "source_winder": 5,
                "product_id": product_id,
            },
        )
    ]

    db_session.add(p3)
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={
            "machine_no": "p 24",
            "product_id": "2025_01_03_P24_M1_1234567-01",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] == 1
    assert payload["records"][0]["data_type"] == "P3"
    assert payload["records"][0]["lot_no"] == lot


@pytest.mark.asyncio
async def test_v2_advanced_query_normalizes_lot_no_hyphen_and_underscore(
    client, db_session
):
    tenant = await _create_tenant(db_session)

    lot = "2507173_02"
    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=normalize_lot_no(lot),
        production_date_yyyymmdd=20250103,
        machine_no="P24",
        mold_no="M1",
        product_id=f"2025-01-03-P24-M1-{lot}",
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
        )
    ]
    db_session.add(p3)
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={"lot_no": "2507173-02"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_count"] == 1
    assert payload["records"][0]["lot_no"] == lot
