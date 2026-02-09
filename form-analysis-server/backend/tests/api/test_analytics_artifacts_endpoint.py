import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
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
async def test_v2_analytics_artifacts_list_ok(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)

    from app.services import analytics_external

    class FakeInfo:
        def __init__(self, key, filename, exists):
            self.key = key
            self.filename = filename
            self.exists = exists
            self.size_bytes = 123
            self.mtime_epoch = 456.0

    monkeypatch.setattr(
        analytics_external,
        "list_analytics_artifacts",
        lambda: [FakeInfo("serialized_events", "ut_serialized_results.json", True)],
    )

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get("/api/v2/analytics/artifacts", headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert isinstance(payload, list)
    assert payload[0]["key"] == "serialized_events"
    assert payload[0]["exists"] is True


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_get_ok(client, monkeypatch, db_session):
    tenant = await _create_tenant(db_session)

    from app.services import analytics_external

    monkeypatch.setattr(
        analytics_external,
        "get_analytics_artifact_list_view",
        lambda key, **_: [
            {
                "event_id": "E-1",
                "event_date": "2025-01-01T00:00:00Z",
                "produce_no": "P",
                "winder": "W",
                "slitting": "S",
                "iqr_count": 1,
                "t2_count": 2,
                "spe_count": 3,
            }
        ],
    )

    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get(
        "/api/v2/analytics/artifacts/serialized_events",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["event_id"] == "E-1"


@pytest.mark.asyncio
async def test_v2_analytics_artifacts_unknown_key_404(client, db_session):
    tenant = await _create_tenant(db_session)
    headers = {"X-Tenant-Id": str(tenant.id)}
    resp = await client.get("/api/v2/analytics/artifacts/not_a_real_key", headers=headers)
    assert resp.status_code == 404
