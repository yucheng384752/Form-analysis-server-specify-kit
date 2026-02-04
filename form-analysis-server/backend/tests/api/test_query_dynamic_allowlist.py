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
async def test_v2_query_dynamic_allows_machine_contains(client, db_session):
    tenant = await _create_tenant(db_session)

    lot = "1234567_01"
    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=normalize_lot_no(lot),
        production_date_yyyymmdd=20250103,
        machine_no="P24",
        mold_no="M1",
        product_id=f"2025-01-03-P24-M1-{lot}",
        extras={"rows": [{"specification": "PE 32"}]},
        created_at=datetime(2025, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
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
    resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={
            "data_type": "P3",
            "filters": [
                {"field": "machine_no", "op": "contains", "value": "P24"},
            ],
            "page": 1,
            "page_size": 50,
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_count"] == 1
    assert payload["records"][0]["data_type"] == "P3"
    assert payload["records"][0]["lot_no"] == lot


@pytest.mark.asyncio
async def test_v2_query_dynamic_rejects_unknown_field(client, db_session):
    tenant = await _create_tenant(db_session)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={
            "data_type": "P3",
            "filters": [
                {"field": "tenant_id", "op": "eq", "value": str(tenant.id)},
            ],
        },
        headers=headers,
    )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_v2_query_dynamic_rejects_invalid_operator(client, db_session):
    tenant = await _create_tenant(db_session)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={
            "data_type": "P3",
            "filters": [
                {"field": "machine_no", "op": "gt", "value": "P24"},
            ],
        },
        headers=headers,
    )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_v2_query_dynamic_allows_row_data_key_contains(client, db_session):
    tenant = await _create_tenant(db_session)

    lot_ok = "1234567_01"
    p3_ok = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_ok,
        lot_no_norm=normalize_lot_no(lot_ok),
        production_date_yyyymmdd=20250103,
        machine_no="P24",
        mold_no="M1",
        product_id=f"2025-01-03-P24-M1-{lot_ok}",
        extras={"rows": [{"specification": "PE 32"}]},
        created_at=datetime(2025, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
    )
    p3_ok.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_ok,
            source_winder=5,
            specification="PE 32",
            row_data={"customer": "ACME"},
        )
    ]

    lot_other = "1234567_02"
    p3_other = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_other,
        lot_no_norm=normalize_lot_no(lot_other),
        production_date_yyyymmdd=20250103,
        machine_no="P24",
        mold_no="M1",
        product_id=f"2025-01-03-P24-M1-{lot_other}",
        extras={"rows": [{"specification": "PE 32"}]},
        created_at=datetime(2025, 1, 3, 0, 0, 1, tzinfo=timezone.utc),
    )
    p3_other.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_other,
            source_winder=5,
            specification="PE 32",
            row_data={"customer": "OTHER"},
        )
    ]

    db_session.add_all([p3_ok, p3_other])
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={
            "data_type": "P3",
            "filters": [
                {"field": "row_data.customer", "op": "contains", "value": "ACME"},
            ],
            "page": 1,
            "page_size": 50,
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_count"] == 1
    assert payload["records"][0]["lot_no"] == lot_ok


@pytest.mark.asyncio
async def test_v2_query_dynamic_rejects_invalid_row_data_key(client, db_session):
    tenant = await _create_tenant(db_session)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={
            "data_type": "P3",
            "filters": [
                {"field": "row_data.bad.key", "op": "contains", "value": "x"},
            ],
        },
        headers=headers,
    )

    assert resp.status_code == 400
