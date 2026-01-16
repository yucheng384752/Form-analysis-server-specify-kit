import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app, settings


@pytest.fixture
async def client(db_session_clean):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    prev_admin_keys = getattr(settings, "admin_api_keys_str", "")
    settings.admin_api_keys_str = "test-admin-key"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    settings.admin_api_keys_str = prev_admin_keys
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_tenants_initially_empty(client):
    resp = await client.get("/api/tenants")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data == []


@pytest.mark.asyncio
async def test_create_tenant_only_when_empty_then_409(client):
    # Create with empty JSON body -> should use defaults.
    create = await client.post("/api/tenants", json={}, headers={"X-Admin-API-Key": "test-admin-key"})
    assert create.status_code == 201, create.text

    body = create.json()
    assert set(body.keys()) >= {"id", "name", "code", "is_active"}
    uuid.UUID(str(body["id"]))
    assert body["name"] == "UT"
    assert body["code"] == "ut"
    assert body["is_active"] is True

    # Second create must be blocked.
    create2 = await client.post("/api/tenants", json={}, headers={"X-Admin-API-Key": "test-admin-key"})
    assert create2.status_code == 409, create2.text
    assert create2.json().get("detail") == "Tenant already exists"

    # GET should now return exactly 1 active tenant.
    resp = await client.get("/api/tenants")
    assert resp.status_code == 200, resp.text
    tenants = resp.json()
    assert isinstance(tenants, list)
    assert len(tenants) == 1
    assert tenants[0]["id"] == body["id"]
