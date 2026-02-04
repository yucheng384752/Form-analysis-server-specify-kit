import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant
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
async def test_v2_trace_detail_uses_items_rows_when_record_extras_empty(
    client, db_session_clean
):
    tenant = await _create_tenant(db_session_clean)

    lot_no_raw = "2507173_02"
    lot_no_norm = normalize_lot_no(lot_no_raw)

    # P2: create record + item row_data, but keep record.extras empty
    p2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no_raw,
        lot_no_norm=lot_no_norm,
        winder_number=5,
        extras={},
        created_at=datetime(2025, 9, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    db_session_clean.add(p2)
    await db_session_clean.flush()

    db_session_clean.add(
        P2ItemV2(
            p2_record_id=p2.id,
            tenant_id=tenant.id,
            winder_number=5,
            row_data={"format": "P2-FORMAT", "hello": "world"},
        )
    )

    # P3: create record + item row_data, but keep record.extras empty
    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no_raw,
        lot_no_norm=lot_no_norm,
        production_date_yyyymmdd=20250902,
        machine_no="UNKNOWN",
        mold_no="UNKNOWN",
        product_id="20250902_P24_238-2_301",
        extras={},
        created_at=datetime(2025, 9, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    db_session_clean.add(p3)
    await db_session_clean.flush()

    db_session_clean.add(
        P3ItemV2(
            p3_record_id=p3.id,
            tenant_id=tenant.id,
            row_no=1,
            product_id=None,
            lot_no=lot_no_raw,
            production_date=date(2025, 9, 2),
            machine_no="P24",
            mold_no="238-2",
            production_lot=301,
            source_winder=5,
            specification="SPEC-A",
            row_data={"P3_No.": "2507173_02_05"},
        )
    )

    await db_session_clean.commit()

    resp = await client.get(
        f"/api/v2/query/trace/{lot_no_norm}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200

    payload = resp.json()

    # P2 rows should come from items_v2 (not empty record.extras)
    assert isinstance(payload.get("p2"), list)
    assert payload["p2"], payload
    p2_extras = payload["p2"][0].get("extras")
    assert isinstance(p2_extras, dict)
    p2_rows = p2_extras.get("rows")
    assert isinstance(p2_rows, list)
    assert p2_rows[0].get("winder_number") == 5
    assert p2_rows[0].get("hello") == "world"

    # P3 rows should come from items_v2
    assert isinstance(payload.get("p3"), list)
    assert payload["p3"], payload
    p3_row_container = payload["p3"][0]
    p3_extras = p3_row_container.get("extras")
    assert isinstance(p3_extras, dict)
    p3_rows = p3_extras.get("rows")
    assert isinstance(p3_rows, list)
    assert p3_rows[0].get("P3_No.") == "2507173_02_05"

    # UNKNOWN machine/mold should be derived from items (or extras)
    assert p3_row_container.get("machine_no") == "P24"
    assert p3_row_container.get("mold_no") == "238-2"
