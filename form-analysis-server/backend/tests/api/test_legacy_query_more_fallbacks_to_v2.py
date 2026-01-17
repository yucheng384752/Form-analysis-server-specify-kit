import uuid
from datetime import date

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_db
from app.models.core.tenant import Tenant
from app.models.p3_record import P3Record
from app.models.p3_item_v2 import P3ItemV2
from app.models.record import Record, DataType
from app.models.p3_item import P3Item
from app.utils.normalization import normalize_lot_no


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def _seed_tenant_with_p3(db_session) -> tuple[Tenant, str, uuid.UUID]:
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

    return tenant, lot_no, p3.id


@pytest.mark.asyncio
async def test_legacy_records_falls_back_to_v2_when_no_legacy_records(client, db_session):
    tenant, lot_no, _ = await _seed_tenant_with_p3(db_session)

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
async def test_legacy_records_does_not_fall_back_to_legacy_when_tenant_provided(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()

    # Seed legacy-only Record data that would match legacy `/api/query/records`.
    legacy_lot_no = f"LEGACY_RECORDS_{uuid.uuid4().hex[:8]}"
    legacy = Record(
        lot_no=legacy_lot_no,
        data_type=DataType.P1,
    )
    db_session.add(legacy)
    await db_session.commit()

    # With tenant context, results should come from v2 only (empty here).
    resp = await client.get(
        "/api/query/records",
        params={"lot_no": legacy_lot_no, "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["total_count"] == 0
    assert payload["records"] == []


@pytest.mark.asyncio
async def test_legacy_lot_suggestions_falls_back_to_v2_when_no_legacy_records(client, db_session):
    tenant, lot_no, _ = await _seed_tenant_with_p3(db_session)

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
async def test_legacy_lot_suggestions_does_not_fall_back_to_legacy_when_tenant_provided(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()

    # Seed a legacy-only Record lot suggestion.
    legacy_lot_no = f"LEGACY_ONLY_{uuid.uuid4().hex[:8]}"
    legacy = Record(
        lot_no=legacy_lot_no,
        data_type=DataType.P1,
    )
    db_session.add(legacy)
    await db_session.commit()

    # With tenant context, suggestions should come from v2 only (empty here).
    resp = await client.get(
        "/api/query/lots/suggestions",
        params={"query": "LEGACY_ONLY", "limit": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    suggestions = resp.json()
    assert isinstance(suggestions, list)
    assert suggestions == []


@pytest.mark.asyncio
async def test_legacy_field_options_does_not_fall_back_to_legacy_when_tenant_provided(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()

    # Seed a legacy-only P3Item machine_no option.
    legacy_lot_no = f"LEGACY_ONLY_{uuid.uuid4().hex[:8]}"
    legacy_record = Record(
        lot_no=legacy_lot_no,
        data_type=DataType.P3,
    )
    db_session.add(legacy_record)
    await db_session.flush()

    legacy_item = P3Item(
        record_id=legacy_record.id,
        row_no=1,
        lot_no=legacy_record.lot_no,
        machine_no="P99",
    )
    db_session.add(legacy_item)
    await db_session.commit()

    # With tenant context, options should come from v2 only (empty here).
    resp = await client.get(
        "/api/query/options/machine_no",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    options = resp.json()
    assert isinstance(options, list)
    assert options == []


@pytest.mark.asyncio
async def test_legacy_field_options_falls_back_to_v2_when_no_legacy_records(client, db_session):
    tenant, _, _ = await _seed_tenant_with_p3(db_session)

    resp = await client.get(
        "/api/query/options/machine_no",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    options = resp.json()
    assert isinstance(options, list)
    assert "P24" in options


@pytest.mark.asyncio
async def test_legacy_field_options_bottom_tape_lot_maps_to_v2_mold_no(client, db_session):
    tenant, _, _ = await _seed_tenant_with_p3(db_session)

    resp = await client.get(
        "/api/query/options/bottom_tape_lot",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    options = resp.json()
    assert isinstance(options, list)
    assert "M1" in options


@pytest.mark.asyncio
async def test_legacy_field_options_product_id_falls_back_to_v2(client, db_session):
    tenant, _, _ = await _seed_tenant_with_p3(db_session)

    resp = await client.get(
        "/api/query/options/product_id",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    options = resp.json()
    assert isinstance(options, list)
    assert any(v.startswith("2025-01-01-P24-M1-") for v in options)


@pytest.mark.asyncio
async def test_legacy_lot_groups_falls_back_to_v2_when_no_legacy_records(client, db_session):
    tenant, lot_no, _ = await _seed_tenant_with_p3(db_session)

    resp = await client.get(
        "/api/query/lots",
        params={"search": "2507", "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["total_count"] >= 1
    assert any(g["lot_no"] == lot_no for g in payload["groups"])


@pytest.mark.asyncio
async def test_legacy_lot_groups_does_not_fall_back_to_legacy_when_tenant_provided(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()

    # Seed legacy-only Record data that would show up in legacy grouping.
    legacy_lot_no = f"LEGACY_GROUP_{uuid.uuid4().hex[:8]}"
    legacy = Record(
        lot_no=legacy_lot_no,
        data_type=DataType.P1,
    )
    db_session.add(legacy)
    await db_session.commit()

    # With tenant context, lot groups should come from v2 only (empty here).
    resp = await client.get(
        "/api/query/lots",
        params={"search": "LEGACY_GROUP", "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["total_count"] == 0
    assert payload["groups"] == []


@pytest.mark.asyncio
async def test_legacy_record_stats_does_not_fall_back_to_legacy_when_tenant_provided(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()

    # Seed legacy-only Record data that would show up in legacy stats.
    legacy_lot_no = f"LEGACY_STATS_{uuid.uuid4().hex[:8]}"
    legacy = Record(
        lot_no=legacy_lot_no,
        data_type=DataType.P1,
        production_date=date(2025, 1, 1),
    )
    db_session.add(legacy)
    await db_session.commit()

    # With tenant context, stats should come from v2 only (empty here).
    resp = await client.get(
        "/api/query/records/stats",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["total_records"] == 0
    assert payload["unique_lots"] == 0
    assert payload["p1_records"] == 0
    assert payload["p2_records"] == 0
    assert payload["p3_records"] == 0
    assert payload["latest_production_date"] is None
    assert payload["earliest_production_date"] is None


@pytest.mark.asyncio
async def test_legacy_records_advanced_falls_back_to_v2_when_no_legacy_records(client, db_session):
    tenant, lot_no, _ = await _seed_tenant_with_p3(db_session)

    resp = await client.get(
        "/api/query/records/advanced",
        params={"machine_no": "P24", "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["total_count"] >= 1
    assert any(r["lot_no"] == lot_no and r["data_type"] == "P3" for r in payload["records"])


@pytest.mark.asyncio
async def test_legacy_records_advanced_does_not_fall_back_to_legacy_when_tenant_provided(client, db_session):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code=f"test_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session.add(tenant)
    await db_session.commit()

    # Seed legacy-only Record data that would match legacy advanced search.
    legacy_lot_no = f"LEGACY_ADV_{uuid.uuid4().hex[:8]}"
    legacy = Record(
        lot_no=legacy_lot_no,
        data_type=DataType.P1,
    )
    db_session.add(legacy)
    await db_session.commit()

    # With tenant context, advanced results should come from v2 only (empty here).
    resp = await client.get(
        "/api/query/records/advanced",
        params={"lot_no": legacy_lot_no, "page": 1, "page_size": 10},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["total_count"] == 0
    assert payload["records"] == []


@pytest.mark.asyncio
async def test_legacy_get_record_falls_back_to_v2_when_record_missing_in_legacy(client, db_session):
    tenant, _, p3_id = await _seed_tenant_with_p3(db_session)

    resp = await client.get(
        f"/api/query/records/{p3_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["id"] == str(p3_id)
    assert payload["data_type"] == "P3"
