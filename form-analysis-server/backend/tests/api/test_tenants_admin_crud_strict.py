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
async def test_admin_create_additional_tenant_and_delete_soft(client):
    # Bootstrap-only create works once.
    create1 = await client.post(
        "/api/tenants", json={}, headers={"X-Admin-API-Key": "test-admin-key"}
    )
    assert create1.status_code == 201, create1.text
    t1 = create1.json()
    uuid.UUID(str(t1["id"]))

    # Admin CRUD create can add more tenants.
    create2 = await client.post(
        "/api/tenants/admin",
        json={
            "name": "Tenant Two",
            "code": "t2",
            "is_active": True,
            "is_default": False,
        },
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert create2.status_code == 201, create2.text
    t2 = create2.json()
    assert t2["code"] == "t2"
    assert t2["is_active"] is True

    # Deleting is a soft delete (is_active=false) and requires admin key.
    delete = await client.delete(
        f"/api/tenants/{t2['id']}", headers={"X-Admin-API-Key": "test-admin-key"}
    )
    assert delete.status_code == 200, delete.text
    deleted = delete.json()
    assert deleted["id"] == t2["id"]
    assert deleted["is_active"] is False

    # Without include_inactive, inactive tenants are hidden.
    get_active = await client.get("/api/tenants")
    assert get_active.status_code == 200, get_active.text
    active_rows = get_active.json()
    assert isinstance(active_rows, list)
    assert all(r.get("is_active") is True for r in active_rows)
    assert t2["id"] not in [r.get("id") for r in active_rows]

    # With include_inactive + admin key, include inactive tenants.
    get_all = await client.get(
        "/api/tenants?include_inactive=true",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert get_all.status_code == 200, get_all.text
    all_rows = get_all.json()
    ids = [r.get("id") for r in all_rows]
    assert t1["id"] in ids
    assert t2["id"] in ids
