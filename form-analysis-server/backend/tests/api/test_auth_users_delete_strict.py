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
async def test_admin_can_delete_user_soft(client):
    # Bootstrap tenant.
    t = await client.post(
        "/api/tenants", json={}, headers={"X-Admin-API-Key": "test-admin-key"}
    )
    assert t.status_code == 201, t.text
    tenant = t.json()
    assert tenant.get("code") == "ut"

    # Create user in that tenant using admin key.
    create = await client.post(
        "/api/auth/users",
        json={
            "tenant_code": "ut",
            "username": "u1",
            "password": "password-123",
            "role": "user",
        },
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert create.status_code == 201, create.text
    user = create.json()
    user_id = user.get("id")
    assert user_id
    assert user.get("is_active") is True

    # Delete (deactivate).
    deleted = await client.delete(
        f"/api/auth/users/{user_id}", headers={"X-Admin-API-Key": "test-admin-key"}
    )
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body.get("id") == user_id
    assert body.get("is_active") is False
