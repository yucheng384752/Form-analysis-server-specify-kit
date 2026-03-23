import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant
from app.models.p2_item_v2 import P2ItemV2
from app.models.p2_record import P2Record
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


@pytest.mark.asyncio
async def test_advanced_query_p2_merges_winders_into_one_card(client, db_session):
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

    p2_w1 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        winder_number=1,
        extras={"rows": [{"format": "P2-FORMAT", "winder_number": 1}]},
    )
    p2_w1.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=1,
            row_data={"format": "P2-FORMAT", "winder_number": 1},
        )
    ]

    p2_w2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        winder_number=2,
        extras={"rows": [{"format": "P2-FORMAT", "winder_number": 2}]},
    )
    p2_w2.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=2,
            row_data={"format": "P2-FORMAT", "winder_number": 2},
        )
    ]

    db_session.add_all([p2_w1, p2_w2])
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}

    # P2 only search should return ONE card per lot (merged rows).
    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={"lot_no": lot_no, "data_type": "P2"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] == 1
    assert len(payload["records"]) == 1

    rec = payload["records"][0]
    assert rec["data_type"] == "P2"
    rows = rec.get("additional_data", {}).get("rows", [])
    assert len(rows) == 2
    assert [r.get("winder_number") for r in rows] == [1, 2]


@pytest.mark.asyncio
async def test_advanced_query_p2_winder_filter_still_returns_one_card(
    client, db_session
):
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

    p2_w1 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        winder_number=1,
        extras={"rows": [{"format": "P2-FORMAT", "winder_number": 1}]},
    )
    p2_w1.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=1,
            row_data={"format": "P2-FORMAT", "winder_number": 1},
        )
    ]

    p2_w2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        winder_number=2,
        extras={"rows": [{"format": "P2-FORMAT", "winder_number": 2}]},
    )
    p2_w2.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=2,
            row_data={"format": "P2-FORMAT", "winder_number": 2},
        )
    ]

    db_session.add_all([p2_w1, p2_w2])
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}

    # Winder filter should prune rows, but still keep ONE card.
    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={"lot_no": lot_no, "data_type": "P2", "winder_number": "2"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] == 1
    assert len(payload["records"]) == 1

    rec = payload["records"][0]
    assert rec["data_type"] == "P2"
    rows = rec.get("additional_data", {}).get("rows", [])
    assert len(rows) == 1
    assert rows[0].get("winder_number") == 2
