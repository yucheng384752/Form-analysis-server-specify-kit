import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant
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
        name=f"Trace Tenant {uuid.uuid4()}",
        code=f"trace_tenant_{uuid.uuid4()}",
        is_default=True,
    )
    db_session_clean.add(tenant)
    await db_session_clean.commit()
    await db_session_clean.refresh(tenant)
    return tenant


@pytest.mark.asyncio
async def test_traceability_product_accepts_lot_winder_input(client, db_session_clean):
    tenant = await _create_tenant(db_session_clean)
    lot_no_raw = "2507173_02"

    p3_record = P3Record(
        tenant_id=tenant.id,
        lot_no_raw=lot_no_raw,
        lot_no_norm=normalize_lot_no(lot_no_raw),
        production_date_yyyymmdd=20250717,
        machine_no="P24",
        mold_no="238-4",
        product_id="20250717_P24_238-4_301",
        extras={},
        created_at=datetime(2025, 7, 17, 0, 0, 0, tzinfo=timezone.utc),
    )
    db_session_clean.add(p3_record)
    await db_session_clean.flush()

    db_session_clean.add(
        P3ItemV2(
            p3_record_id=p3_record.id,
            tenant_id=tenant.id,
            row_no=1,
            product_id="20250717_P24_238-4_301",
            lot_no=lot_no_raw,
            production_date=date(2025, 7, 17),
            machine_no="P24",
            mold_no="238-4",
            production_lot=301,
            source_winder=19,
            row_data={"lot no": "2507173_02_19"},
        )
    )
    await db_session_clean.commit()

    for candidate in ["2507173_02_19", "2507173-02-19"]:
        resp = await client.get(
            f"/api/traceability/product/{candidate}",
            headers={"X-Tenant-Id": str(tenant.id)},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload.get("p3", {}).get("lot_no") == lot_no_raw
        assert payload.get("p3", {}).get("source_winder") == 19

