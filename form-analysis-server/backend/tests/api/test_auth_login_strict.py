import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app
from app.core.password import hash_password
from app.models.core.tenant import Tenant
from app.models.core.tenant_user import TenantUser


@pytest.fixture
async def client(db_session_clean):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_auth_login_returns_api_key_and_tenant_id(db_session_clean, client):
    tenant = Tenant(name="UT", code="ut", is_active=True, is_default=True)
    db_session_clean.add(tenant)
    await db_session_clean.commit()
    await db_session_clean.refresh(tenant)

    user = TenantUser(tenant_id=tenant.id, username="user", password_hash=hash_password("password123"), role="user", is_active=True)
    db_session_clean.add(user)
    await db_session_clean.commit()

    res = await client.post(
        "/api/auth/login",
        json={"tenant_code": "ut", "username": "user", "password": "password123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("tenant_id")
    assert data.get("tenant_code") == "ut"
    assert data.get("api_key")
