import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.utils.normalization import normalize_lot_no


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_legacy_records_stats_prefers_v2_tenant_scoped(client, db_session):
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

    db_session.add(
        P1Record(
            tenant_id=tenant.id,
            lot_no_raw=lot_no,
            lot_no_norm=lot_no_norm,
            extras={},
            created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
    )
    db_session.add(
        P2Record(
            tenant_id=tenant.id,
            lot_no_raw=lot_no,
            lot_no_norm=lot_no_norm,
            winder_number=1,
            extras={},
            created_at=datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        )
    )
    db_session.add(
        P3Record(
            tenant_id=tenant.id,
            lot_no_raw=lot_no,
            lot_no_norm=lot_no_norm,
            production_date_yyyymmdd=20250101,
            machine_no="P24",
            mold_no="M1",
            product_id="2025-01-01-P24-M1-2507173_02",
            extras={},
            created_at=datetime(2025, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
        )
    )

    await db_session.commit()

    headers = {"X-Tenant-Id": str(tenant.id)}

    legacy_resp = await client.get("/api/query/records/stats", headers=headers)
    assert legacy_resp.status_code == 200, legacy_resp.text
    legacy_payload = legacy_resp.json()

    assert legacy_payload["total_records"] == 3
    assert legacy_payload["unique_lots"] == 1
    assert legacy_payload["p1_records"] == 1
    assert legacy_payload["p2_records"] == 1
    assert legacy_payload["p3_records"] == 1
    assert legacy_payload["earliest_production_date"] == "2025-01-01"
    assert legacy_payload["latest_production_date"] == "2025-01-01"

    v2_resp = await client.get("/api/v2/query/records/stats", headers=headers)
    assert v2_resp.status_code == 200, v2_resp.text
    v2_payload = v2_resp.json()

    assert v2_payload == legacy_payload
