import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.p2_item_v2 import P2ItemV2
from app.models.p2_record import P2Record
from app.models.p3_item_v2 import P3ItemV2
from app.models.p3_record import P3Record
from app.utils.normalization import normalize_lot_no


@pytest.fixture
async def client(db_session_clean):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
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
async def test_dynamic_date_range_excludes_out_of_range_and_null_dates(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)

    lot = "2507173_02"
    lot_norm = normalize_lot_no(lot)

    # P1: out of range (2025-07-17)
    p1 = P1Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=lot_norm,
        extras={"rows": [{"Production Date": "250717"}]},
        created_at=datetime(2025, 7, 17, 0, 0, 0, tzinfo=timezone.utc),
    )

    # P2: no parseable production_date (null production_date in query result)
    p2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=lot_norm,
        winder_number=1,
        extras={"rows": [{"format": "PE32", "Semi-finished productsLOT NO": lot}]},
        created_at=datetime(2025, 8, 20, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=1,
            row_data={"format": "PE32", "Semi-finished productsLOT NO": lot},
        )
    ]

    # P3: in range (2025-09-02)
    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=lot_norm,
        production_date_yyyymmdd=20250902,
        machine_no="P24",
        mold_no="238-2",
        product_id="20250902_P24_238-2_301",
        extras={"rows": [{"specification": "PE 32"}]},
        created_at=datetime(2025, 9, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    p3.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot,
            source_winder=1,
            specification="PE 32",
            row_data={"specification": "PE 32", "source_winder": 1},
        )
    ]

    db_session_clean.add_all([p1, p2, p3])
    await db_session_clean.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    payload = {
        "filters": [
            {
                "field": "production_date",
                "op": "between",
                "value": ["2025-08-01", "2025-09-30"],
            }
        ],
        "page": 1,
        "page_size": 50,
    }

    # P1 does not support production_date in dynamic allowlist.
    p1_resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={**payload, "data_type": "P1"},
        headers=headers,
    )
    assert p1_resp.status_code == 400, p1_resp.text
    assert "Unsupported field(s) for data_type P1: production_date" in p1_resp.text

    # P2 should be excluded (null/unparseable production_date)
    p2_resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={**payload, "data_type": "P2"},
        headers=headers,
    )
    assert p2_resp.status_code == 200, p2_resp.text
    p2_body = p2_resp.json()
    assert p2_body["total_count"] == 0
    assert p2_body["records"] == []

    # P3 should remain (in range)
    p3_resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={**payload, "data_type": "P3"},
        headers=headers,
    )
    assert p3_resp.status_code == 200, p3_resp.text
    p3_body = p3_resp.json()
    assert p3_body["total_count"] == 1
    assert len(p3_body["records"]) == 1
    assert p3_body["records"][0]["production_date"] == "2025-09-02"


@pytest.mark.asyncio
async def test_dynamic_date_range_includes_p2_when_date_exists_in_nested_rows(
    client, db_session_clean
):
    tenant = await _create_tenant(db_session_clean)

    lot = "2508203_03"
    lot_norm = normalize_lot_no(lot)

    p2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=lot_norm,
        winder_number=1,
        extras={"rows": [{"format": "PE32"}]},
        created_at=datetime(2025, 8, 20, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=1,
            row_data={
                "rows": [
                    {
                        "Slitting date": "2025/08/20",
                        "format": "PE32",
                        "Semi-finished productsLOT NO": lot,
                    }
                ]
            },
        )
    ]

    db_session_clean.add(p2)
    await db_session_clean.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    payload = {
        "data_type": "P2",
        "filters": [
            {
                "field": "production_date",
                "op": "between",
                "value": ["2025-08-01", "2025-08-31"],
            }
        ],
        "page": 1,
        "page_size": 50,
    }

    resp = await client.post("/api/v2/query/records/dynamic", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_count"] == 1
    assert len(body["records"]) == 1
    assert body["records"][0]["data_type"] == "P2"
    assert body["records"][0]["production_date"] == "2025-08-20"


@pytest.mark.asyncio
async def test_dynamic_date_range_prefers_structured_p2_item_date_column(
    client, db_session_clean
):
    tenant = await _create_tenant(db_session_clean)

    lot = "2508203_04"
    lot_norm = normalize_lot_no(lot)

    p2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot,
        lot_no_norm=lot_norm,
        winder_number=2,
        extras={"rows": [{"format": "PE32"}]},
        created_at=datetime(2025, 8, 21, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=2,
            production_date_yyyymmdd=20250821,
            row_data={"format": "PE32", "Semi-finished productsLOT NO": lot},
        )
    ]

    db_session_clean.add(p2)
    await db_session_clean.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    payload = {
        "data_type": "P2",
        "filters": [
            {
                "field": "production_date",
                "op": "between",
                "value": ["2025-08-01", "2025-08-31"],
            }
        ],
        "page": 1,
        "page_size": 50,
    }

    resp = await client.post("/api/v2/query/records/dynamic", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_count"] == 1
    assert len(body["records"]) == 1
    assert body["records"][0]["data_type"] == "P2"
    assert body["records"][0]["production_date"] == "2025-08-21"
