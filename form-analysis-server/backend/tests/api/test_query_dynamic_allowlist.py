import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, text

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant
from app.models.p2_item_v2 import P2ItemV2
from app.models.p2_record import P2Record
from app.models.p3_item_v2 import P3ItemV2
from app.models.p3_record import P3Record
from app.services.csv_field_mapper import csv_field_mapper
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
async def test_v2_query_dynamic_allows_missing_data_type(client, db_session):
    tenant = await _create_tenant(db_session)

    lot = "1234567_11"
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
            "filters": [{"field": "machine_no", "op": "contains", "value": "P24"}],
            "page": 1,
            "page_size": 50,
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_count"] == 1
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
async def test_v2_query_dynamic_rejects_incompatible_field_for_p1(client, db_session):
    tenant = await _create_tenant(db_session)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={
            "data_type": "P1",
            "filters": [{"field": "winder_number", "op": "eq", "value": 5}],
        },
        headers=headers,
    )

    assert resp.status_code == 400
    assert "Unsupported field(s) for data_type P1" in resp.text


@pytest.mark.asyncio
async def test_v2_query_dynamic_rejects_incompatible_field_for_p3(client, db_session):
    tenant = await _create_tenant(db_session)

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={
            "data_type": "P3",
            "filters": [{"field": "thickness", "op": "between", "value": [30, 33]}],
        },
        headers=headers,
    )

    assert resp.status_code == 400
    assert "Unsupported field(s) for data_type P3" in resp.text


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


@pytest.mark.asyncio
async def test_v2_query_dynamic_p2_winder_and_striped_results_eq_zero(
    client, db_session
):
    tenant = await _create_tenant(db_session)

    lot_ng_num = "2234567_20"
    lot_ng_str = "2234568_20"
    lot_ok = "2234569_20"
    lot_other_winder = "2234570_20"

    p2_ng_num = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_ng_num,
        lot_no_norm=normalize_lot_no(lot_ng_num),
        winder_number=20,
        extras={"rows": [{"Striped Results": 0}]},
        created_at=datetime(2025, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2_ng_num.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=20,
            row_data={"Striped Results": 0},
        )
    ]

    p2_ng_str = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_ng_str,
        lot_no_norm=normalize_lot_no(lot_ng_str),
        winder_number=20,
        extras={"rows": [{"Striped Results": "0"}]},
        created_at=datetime(2025, 1, 3, 0, 0, 1, tzinfo=timezone.utc),
    )
    p2_ng_str.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=20,
            row_data={"Striped Results": "0"},
        )
    ]

    p2_ok = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_ok,
        lot_no_norm=normalize_lot_no(lot_ok),
        winder_number=20,
        extras={"rows": [{"Striped Results": 1}]},
        created_at=datetime(2025, 1, 3, 0, 0, 2, tzinfo=timezone.utc),
    )
    p2_ok.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=20,
            row_data={"Striped Results": 1},
        )
    ]

    p2_other_winder = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_other_winder,
        lot_no_norm=normalize_lot_no(lot_other_winder),
        winder_number=19,
        extras={"rows": [{"Striped Results": 0}]},
        created_at=datetime(2025, 1, 3, 0, 0, 3, tzinfo=timezone.utc),
    )
    p2_other_winder.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=19,
            row_data={"Striped Results": 0},
        )
    ]

    db_session.add_all([p2_ng_num, p2_ng_str, p2_ok, p2_other_winder])
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}

    async def _query_with_result_value(v):
        return await client.post(
            "/api/v2/query/records/dynamic",
            json={
                "data_type": "P2",
                "filters": [
                    {"field": "winder_number", "op": "eq", "value": 20},
                    {"field": "row_data.Striped Results", "op": "eq", "value": v},
                ],
                "page": 1,
                "page_size": 50,
            },
            headers=headers,
        )

    for expected_zero in (0, "0"):
        resp = await _query_with_result_value(expected_zero)
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["total_count"] == 2
        lots = {str(r.get("lot_no")) for r in payload.get("records", [])}
        assert lots == {lot_ng_num, lot_ng_str}


@pytest.mark.asyncio
async def test_v2_query_dynamic_p2_winder_and_striped_results_alias_with_date_range(
    client, db_session
):
    tenant = await _create_tenant(db_session)

    lot_in_range_lower = "2234567_30"
    lot_in_range_alias = "2234568_30"
    lot_other_winder = "2234569_30"
    lot_out_of_range = "2234570_30"

    p2_in_range_lower = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_in_range_lower,
        lot_no_norm=normalize_lot_no(lot_in_range_lower),
        winder_number=30,
        extras={"rows": [{"Striped results": 0}]},
        created_at=datetime(2025, 9, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2_in_range_lower.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=30,
            production_date_yyyymmdd=20250901,
            row_data={"Striped results": 0},
        )
    ]

    p2_in_range_alias = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_in_range_alias,
        lot_no_norm=normalize_lot_no(lot_in_range_alias),
        winder_number=30,
        extras={"rows": [{"striped result": 0}]},
        created_at=datetime(2025, 9, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2_in_range_alias.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=30,
            production_date_yyyymmdd=20250902,
            row_data={"striped result": 0},
        )
    ]

    p2_other_winder = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_other_winder,
        lot_no_norm=normalize_lot_no(lot_other_winder),
        winder_number=31,
        extras={"rows": [{"Striped Results": 0}]},
        created_at=datetime(2025, 9, 3, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2_other_winder.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=31,
            production_date_yyyymmdd=20250903,
            row_data={"Striped Results": 0},
        )
    ]

    p2_out_of_range = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_out_of_range,
        lot_no_norm=normalize_lot_no(lot_out_of_range),
        winder_number=30,
        extras={"rows": [{"Striped Results": 0}]},
        created_at=datetime(2025, 10, 3, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2_out_of_range.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=30,
            production_date_yyyymmdd=20251003,
            row_data={"Striped Results": 0},
        )
    ]

    db_session.add_all(
        [p2_in_range_lower, p2_in_range_alias, p2_other_winder, p2_out_of_range]
    )
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={
            "data_type": "P2",
            "filters": [
                {"field": "winder_number", "op": "eq", "value": 30},
                {
                    "field": "production_date",
                    "op": "between",
                    "value": ["2025-09-01", "2025-09-30"],
                },
                {"field": "row_data.Striped Results", "op": "eq", "value": 0},
            ],
            "page": 1,
            "page_size": 50,
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_count"] == 2
    lots = {str(r.get("lot_no")) for r in payload.get("records", [])}
    assert lots == {lot_in_range_lower, lot_in_range_alias}


@pytest.mark.asyncio
async def test_v2_query_dynamic_p2_winder_and_striped_results_with_roc_datetime_string(
    client, db_session
):
    tenant = await _create_tenant(db_session)
    assert csv_field_mapper._normalize_date_to_yyyymmdd("114年8月27日14:30") == 20250827

    pragma_result = await db_session.execute(text("PRAGMA table_info(p2_items_v2)"))
    p2_item_columns = {row[1] for row in pragma_result.all()}
    for col_name in ("production_date_yyyymmdd", "trace_lot_no"):
        if col_name not in p2_item_columns:
            await db_session.execute(
                text(
                    "ALTER TABLE p2_items_v2 ADD COLUMN "
                    + col_name
                    + (
                        " INTEGER"
                        if col_name == "production_date_yyyymmdd"
                        else " VARCHAR(32)"
                    )
                )
            )
            p2_item_columns.add(col_name)

    if "production_date_yyyymmdd" not in p2_item_columns:
        await db_session.execute(
            text("ALTER TABLE p2_items_v2 ADD COLUMN production_date_yyyymmdd INTEGER")
        )

    lot_in_range = "2234567_01"
    p2_in_range = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_in_range,
        lot_no_norm=normalize_lot_no(lot_in_range),
        winder_number=1,
        extras={
            "rows": [
                {
                    "Striped Results": 0,
                    "分條時間": "114年8月27日14:30",
                }
            ]
        },
        created_at=datetime(2025, 8, 27, 0, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(p2_in_range)
    await db_session.flush()
    await db_session.execute(
        insert(P2ItemV2).values(
            id=uuid.uuid4(),
            p2_record_id=p2_in_range.id,
            tenant_id=tenant.id,
            winder_number=1,
            row_data={
                "Striped Results": 0,
                "分條時間": "114年8月27日14:30",
                "production_date": "2025-08-27",
            },
            created_at=datetime(2025, 8, 27, 0, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 8, 27, 0, 0, 0, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={
            "data_type": "P2",
            "filters": [
                {"field": "winder_number", "op": "eq", "value": 1},
                {
                    "field": "production_date",
                    "op": "between",
                    "value": ["2025-08-01", "2025-08-31"],
                },
                {"field": "row_data.Striped Results", "op": "eq", "value": 0},
            ],
            "page": 1,
            "page_size": 50,
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_count"] == 1
    assert payload["records"][0]["lot_no"] == lot_in_range


@pytest.mark.asyncio
async def test_v2_query_dynamic_p2_winder_and_slitting_result_eq_zero_materialized(
    client, db_session
):
    tenant = await _create_tenant(db_session)

    lot_hit = "2234567_01"
    lot_miss_value_from_row = "2234568_01"
    lot_other_date = "2234569_01"
    lot_other_winder = "2234570_01"

    p2_hit = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_hit,
        lot_no_norm=normalize_lot_no(lot_hit),
        winder_number=1,
        extras={"rows": [{"Striped Results": 1}]},
        created_at=datetime(2025, 8, 15, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2_hit.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=1,
            production_date_yyyymmdd=20250815,
            slitting_result=0,
            row_data={"Striped Results": 1},
        )
    ]

    p2_miss = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_miss_value_from_row,
        lot_no_norm=normalize_lot_no(lot_miss_value_from_row),
        winder_number=1,
        extras={"rows": [{"Striped Results": 0}]},
        created_at=datetime(2025, 8, 16, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2_miss.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=1,
            production_date_yyyymmdd=20250816,
            slitting_result=1,
            row_data={"Striped Results": 0},
        )
    ]

    p2_other_winder = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_other_winder,
        lot_no_norm=normalize_lot_no(lot_other_winder),
        winder_number=2,
        extras={"rows": [{"Striped Results": 0}]},
        created_at=datetime(2025, 8, 17, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2_other_winder.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=2,
            production_date_yyyymmdd=20250817,
            slitting_result=0,
            row_data={"Striped Results": 0},
        )
    ]

    p2_other_date = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_other_date,
        lot_no_norm=normalize_lot_no(lot_other_date),
        winder_number=1,
        extras={"rows": [{"Striped Results": 0}]},
        created_at=datetime(2025, 7, 30, 0, 0, 0, tzinfo=timezone.utc),
    )
    p2_other_date.items_v2 = [
        P2ItemV2(
            tenant_id=tenant.id,
            winder_number=1,
            production_date_yyyymmdd=20250730,
            slitting_result=0,
            row_data={"Striped Results": 0},
        )
    ]

    db_session.add_all([p2_hit, p2_miss, p2_other_winder, p2_other_date])
    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.post(
        "/api/v2/query/records/dynamic",
        json={
            "data_type": "P2",
            "filters": [
                {"field": "winder_number", "op": "eq", "value": 1},
                {
                    "field": "production_date",
                    "op": "between",
                    "value": ["2025-08-01", "2025-08-31"],
                },
                {"field": "slitting_result", "op": "eq", "value": 0},
            ],
            "page": 1,
            "page_size": 50,
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_count"] == 1
    assert payload["records"][0]["lot_no"] == lot_hit
