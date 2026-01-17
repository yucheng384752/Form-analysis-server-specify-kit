import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant


@pytest.fixture
async def client(db_session_clean):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_v2_records_stats_requires_tenant_id_in_multitenant(client, db_session_clean, clean_db):
    # Two tenants, no unique default -> must specify tenant.
    t1 = Tenant(
        name=f"Tenant {uuid.uuid4()}",
        code=f"tenant_{uuid.uuid4()}",
        is_default=False,
    )
    t2 = Tenant(
        name=f"Tenant {uuid.uuid4()}",
        code=f"tenant_{uuid.uuid4()}",
        is_default=False,
    )

    db_session_clean.add_all([t1, t2])
    await db_session_clean.commit()

    resp = await client.get("/api/v2/query/records/stats")
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert "X-Tenant-Id" in str(body.get("detail"))
