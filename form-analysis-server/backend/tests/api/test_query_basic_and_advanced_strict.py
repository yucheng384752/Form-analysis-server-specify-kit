import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant

# Legacy models
from app.models.record import DataType, Record
from app.models.p2_item import P2Item
from app.models.p3_item import P3Item

# V2 models
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.models.p2_item_v2 import P2ItemV2
from app.models.p3_item_v2 import P3ItemV2
from app.utils.normalization import normalize_lot_no


@pytest.fixture
async def client(db_session_clean):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
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


async def _seed_legacy_records_for_pagination(db_session_clean) -> tuple[str, list[str]]:
    lot_no = "1234567_01"

    # Set explicit created_at to make ordering deterministic.
    r1 = Record(
        lot_no=lot_no,
        data_type=DataType.P1,
        production_date=date(2025, 1, 1),
        product_name="P1-A",
        quantity=1,
        notes=None,
        additional_data={},
        created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    r2 = Record(
        lot_no=lot_no,
        data_type=DataType.P2,
        production_date=date(2025, 1, 2),
        product_name=None,
        quantity=None,
        notes=None,
        additional_data={},
        created_at=datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    r3 = Record(
        lot_no=lot_no,
        data_type=DataType.P3,
        production_date=date(2025, 1, 3),
        product_name=None,
        quantity=None,
        notes=None,
        additional_data={},
        created_at=datetime(2025, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
    )

    db_session_clean.add_all([r1, r2, r3])
    await db_session_clean.commit()

    # Return ids as strings
    return lot_no, [str(r1.id), str(r2.id), str(r3.id)]


async def _seed_legacy_p2_with_items(db_session_clean) -> str:
    lot_no = "2507173_02"
    rec = Record(
        lot_no=lot_no,
        data_type=DataType.P2,
        production_date=date(2025, 1, 1),
        additional_data={},
    )
    db_session_clean.add(rec)
    await db_session_clean.flush()

    # Add items without touching relationship attributes to avoid async lazy-load.
    db_session_clean.add_all(
        [
            P2Item(
                record_id=rec.id,
                winder_number=5,
                row_data={"winder_number": 5, "format": "P2-FORMAT-5"},
            ),
            P2Item(
                record_id=rec.id,
                winder_number=7,
                row_data={"winder_number": 7, "format": "P2-FORMAT-7"},
            ),
        ]
    )
    await db_session_clean.commit()
    return lot_no


async def _seed_legacy_p3_with_item(db_session_clean) -> tuple[str, str]:
    lot_no = "2507173_03"
    rec = Record(
        lot_no=lot_no,
        data_type=DataType.P3,
        production_date=date(2025, 1, 2),
        product_name=None,
        quantity=None,
        notes=None,
        additional_data={},
    )
    db_session_clean.add(rec)
    await db_session_clean.flush()

    product_id = "2025-01-02_P24_M1_2507173_03"

    # Add item without touching relationship attributes to avoid async lazy-load.
    db_session_clean.add(
        P3Item(
            record_id=rec.id,
            row_no=1,
            lot_no=lot_no,
            production_date=date(2025, 1, 2),
            machine_no="P24",
            mold_no="M1",
            product_id=product_id,
            source_winder=5,
            specification="PE 32",
            bottom_tape_lot="M250523-06-0159",
            row_data={"specification": "PE 32", "machine_no": "P24"},
        )
    )
    await db_session_clean.commit()
    return lot_no, product_id


async def _seed_v2_all_types(db_session_clean, tenant: Tenant) -> str:
    lot_no = "2507173_02"
    lot_no_norm = normalize_lot_no(lot_no)

    p1 = P1Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        extras={"rows": [{"Specification": "P1-SPEC"}]},
        created_at=datetime(2025, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
    )

    p2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        winder_number=5,
        extras={"rows": [{"format": "P2-FORMAT"}]},
        created_at=datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=5,
            row_data={"format": "P2-FORMAT", "winder_number": 5},
        )
    ]

    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no,
        lot_no_norm=lot_no_norm,
        production_date_yyyymmdd=20250101,
        machine_no="P24",
        mold_no="M1",
        product_id="2025-01-01-P24-M1-2507173_02",
        extras={"rows": [{"specification": "P3-SPEC"}]},
        created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    p3.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_no,
            source_winder=5,
            specification="P3-SPEC",
            row_data={"source_winder": 5, "specification": "P3-SPEC"},
        )
    ]

    db_session_clean.add_all([p1, p2, p3])
    await db_session_clean.commit()
    return lot_no


@pytest.mark.asyncio
async def test_legacy_records_requires_lot_no(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)
    resp = await client.get("/api/query/records", headers={"X-Tenant-Id": str(tenant.id)})
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_legacy_records_pagination_and_ordering(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)
    lot_no, ids = await _seed_legacy_records_for_pagination(db_session_clean)

    resp1 = await client.get(
        "/api/query/records",
        params={"lot_no": lot_no, "page": 1, "page_size": 2},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp1.status_code == 200, resp1.text
    payload1 = resp1.json()

    assert payload1["total_count"] == 3
    assert len(payload1["records"]) == 2

    # created_at desc => r3, r2
    got_ids_page1 = [r["id"] for r in payload1["records"]]
    assert got_ids_page1 == [ids[2], ids[1]]

    resp2 = await client.get(
        "/api/query/records",
        params={"lot_no": lot_no, "page": 2, "page_size": 2},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp2.status_code == 200, resp2.text
    payload2 = resp2.json()
    assert payload2["total_count"] == 3
    assert len(payload2["records"]) == 1
    assert payload2["records"][0]["id"] == ids[0]


@pytest.mark.asyncio
async def test_legacy_records_data_type_filter(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)
    lot_no = "9999999_01"
    r_p1 = Record(
        lot_no=lot_no,
        data_type=DataType.P1,
        production_date=date(2025, 1, 1),
        product_name="P1",
        quantity=1,
        additional_data={},
    )
    r_p3 = Record(
        lot_no=lot_no,
        data_type=DataType.P3,
        production_date=date(2025, 1, 1),
        additional_data={},
    )
    db_session_clean.add_all([r_p1, r_p3])
    await db_session_clean.commit()

    resp = await client.get(
        "/api/query/records",
        params={"lot_no": lot_no, "data_type": "P1", "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_count"] == 1
    assert payload["records"][0]["data_type"] == "P1"

    resp2 = await client.get(
        "/api/query/records",
        params={"lot_no": lot_no, "data_type": "P2", "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp2.status_code == 200, resp2.text
    payload2 = resp2.json()
    assert payload2["total_count"] == 0
    assert payload2["records"] == []


@pytest.mark.asyncio
async def test_legacy_advanced_returns_empty_when_no_conditions(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)
    resp = await client.get("/api/query/records/advanced", headers={"X-Tenant-Id": str(tenant.id)})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_count"] == 0
    assert payload["records"] == []


@pytest.mark.asyncio
async def test_legacy_advanced_winder_filters_p2_items_rows(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)
    await _seed_legacy_p2_with_items(db_session_clean)

    resp = await client.get(
        "/api/query/records/advanced",
        params={"winder_number": 5, "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] == 1
    rec = payload["records"][0]
    assert rec["data_type"] == "P2"

    rows = (rec.get("additional_data") or {}).get("rows")
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].get("winder_number") == 5


@pytest.mark.asyncio
async def test_legacy_advanced_winder_does_not_return_p1_and_can_match_p3(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)
    await _seed_legacy_p2_with_items(db_session_clean)
    await _seed_legacy_p3_with_item(db_session_clean)

    # Seed an unrelated P1 record; winder search must never return it.
    db_session_clean.add(
        Record(
            lot_no="P1_IGNORED",
            data_type=DataType.P1,
            production_date=date(2025, 1, 1),
            additional_data={},
        )
    )
    await db_session_clean.commit()

    resp = await client.get(
        "/api/query/records/advanced",
        params={"winder_number": 5, "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] == 2
    types = {r["data_type"] for r in payload["records"]}
    assert types == {"P2", "P3"}


@pytest.mark.asyncio
async def test_legacy_advanced_p3_filters_machine_and_specification(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)
    lot_no, product_id = await _seed_legacy_p3_with_item(db_session_clean)

    resp = await client.get(
        "/api/query/records/advanced",
        params={"machine_no": "P2", "p3_specification": "PE", "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] == 1
    rec = payload["records"][0]
    assert rec["lot_no"] == lot_no
    assert rec["data_type"] == "P3"

    rows = (rec.get("additional_data") or {}).get("rows")
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].get("product_id") == product_id


@pytest.mark.asyncio
async def test_v2_records_basic_includes_all_types(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)
    lot_no = await _seed_v2_all_types(db_session_clean, tenant)

    resp = await client.get(
        "/api/v2/query/records",
        params={"lot_no": lot_no, "page": 1, "page_size": 50},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] >= 3
    types = {r["data_type"] for r in payload["records"]}
    assert {"P1", "P2", "P3"}.issubset(types)


@pytest.mark.asyncio
async def test_v2_records_data_type_filter_p2_only(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)
    lot_no = await _seed_v2_all_types(db_session_clean, tenant)

    resp = await client.get(
        "/api/v2/query/records",
        params={"lot_no": lot_no, "data_type": "P2", "page": 1, "page_size": 50},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] >= 1
    assert {r["data_type"] for r in payload["records"]} == {"P2"}


@pytest.mark.asyncio
async def test_v2_advanced_filters_machine_and_date_range(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)

    lot_a = "2507173_10"
    lot_b = "2507173_11"

    p3a = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_a,
        lot_no_norm=normalize_lot_no(lot_a),
        production_date_yyyymmdd=20250101,
        machine_no="P24",
        mold_no="M1",
        product_id="PID-A",
        extras={},
    )
    p3a.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_a,
            source_winder=1,
            specification="SPEC-A",
            row_data={"specification": "SPEC-A"},
        )
    ]

    p3b = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_b,
        lot_no_norm=normalize_lot_no(lot_b),
        production_date_yyyymmdd=20250102,
        machine_no="P21",
        mold_no="M1",
        product_id="PID-B",
        extras={},
    )
    p3b.items_v2 = [
        P3ItemV2(
            tenant_id=tenant.id,
            row_no=1,
            lot_no=lot_b,
            source_winder=1,
            specification="SPEC-B",
            row_data={"specification": "SPEC-B"},
        )
    ]

    db_session_clean.add_all([p3a, p3b])
    await db_session_clean.commit()

    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={
            "data_type": "P3",
            "machine_no": "P24",
            "production_date_from": "2025-01-01",
            "production_date_to": "2025-01-01",
            "page": 1,
            "page_size": 50,
        },
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total_count"] == 1
    assert payload["records"][0]["data_type"] == "P3"
    assert payload["records"][0]["lot_no"] == lot_a


@pytest.mark.asyncio
async def test_v2_advanced_invalid_data_type_returns_400(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)

    resp = await client.get(
        "/api/v2/query/records/advanced",
        params={"data_type": "P4", "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 400, resp.text
