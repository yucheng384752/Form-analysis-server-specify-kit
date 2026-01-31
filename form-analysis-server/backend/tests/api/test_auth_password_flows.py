import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.api.deps import get_db
from app.core.password import hash_password
from app.main import app
from app.models.core.tenant import Tenant
from app.models.core.tenant_user import TenantUser


@pytest.fixture(autouse=True)
def _restore_global_settings():
    from app.main import settings

    previous = {
        "auth_mode": getattr(settings, "auth_mode", None),
        "auth_api_key_header": getattr(settings, "auth_api_key_header", None),
        "auth_protect_prefixes_str": getattr(settings, "auth_protect_prefixes_str", None),
        "auth_exempt_paths_str": getattr(settings, "auth_exempt_paths_str", None),
        "admin_api_keys_str": getattr(settings, "admin_api_keys_str", None),
        "admin_api_key_header": getattr(settings, "admin_api_key_header", None),
    }
    yield
    for key, value in previous.items():
        if hasattr(settings, key):
            setattr(settings, key, value)


@pytest.fixture
async def client(db_session_clean, test_engine):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    # Middleware (AUTH_MODE=api_key) uses app.core.database.async_session_factory.
    import app.core.database as database

    previous_factory = database.async_session_factory
    database.async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    database.async_session_factory = previous_factory


async def _create_tenant(db_session_clean, *, code: str) -> Tenant:
    tenant = Tenant(
        name=f"Test Tenant {code} {uuid.uuid4()}",
        code=code,
        is_default=True,
        is_active=True,
    )
    db_session_clean.add(tenant)
    await db_session_clean.commit()
    await db_session_clean.refresh(tenant)
    return tenant


async def _create_user(db_session_clean, *, tenant_id, username: str, role: str, password: str = "password123") -> TenantUser:
    user = TenantUser(
        tenant_id=tenant_id,
        username=username,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db_session_clean.add(user)
    await db_session_clean.commit()
    await db_session_clean.refresh(user)
    return user


async def _login(client: AsyncClient, *, tenant_code: str, username: str, password: str) -> dict:
    resp = await client.post(
        "/api/auth/login",
        json={"tenant_code": tenant_code, "username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_admin_reset_forces_password_change_flow(client, db_session_clean):
    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"

    tenant = await _create_tenant(db_session_clean, code="t1")
    admin = await _create_user(db_session_clean, tenant_id=tenant.id, username="admin", role="admin")
    user = await _create_user(db_session_clean, tenant_id=tenant.id, username="user", role="user")

    admin_login = await _login(client, tenant_code=tenant.code, username=admin.username, password="password123")
    admin_key = admin_login["api_key"]

    reset_resp = await client.post(
        f"/api/auth/users/{user.id}/password-reset",
        json={},
        headers={"X-API-Key": admin_key},
    )
    assert reset_resp.status_code == 200, reset_resp.text
    reset_body = reset_resp.json()
    assert reset_body["user_id"] == str(user.id)
    assert reset_body["must_change_password"] is True
    assert reset_body.get("temporary_password")

    temp_pw = reset_body["temporary_password"]
    user_login = await _login(client, tenant_code=tenant.code, username=user.username, password=temp_pw)
    user_key = user_login["api_key"]
    assert user_login.get("must_change_password") is True

    # Blocked until password is changed.
    blocked = await client.get("/api/audit-events", headers={"X-API-Key": user_key})
    assert blocked.status_code == 403
    assert "Password change required" in blocked.text

    change = await client.post(
        "/api/auth/me/password",
        json={"old_password": temp_pw, "new_password": "newpass123"},
        headers={"X-API-Key": user_key},
    )
    assert change.status_code == 204, change.text

    allowed = await client.get("/api/audit-events", headers={"X-API-Key": user_key})
    assert allowed.status_code == 200, allowed.text

    relogin = await _login(client, tenant_code=tenant.code, username=user.username, password="newpass123")
    assert relogin.get("must_change_password") is False

    old_pw_fail = await client.post(
        "/api/auth/login",
        json={"tenant_code": tenant.code, "username": user.username, "password": temp_pw},
    )
    assert old_pw_fail.status_code == 401


@pytest.mark.asyncio
async def test_manager_cannot_reset_admin_user(client, db_session_clean):
    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"

    tenant = await _create_tenant(db_session_clean, code="t1")
    manager = await _create_user(db_session_clean, tenant_id=tenant.id, username="mgr", role="manager")
    admin = await _create_user(db_session_clean, tenant_id=tenant.id, username="admin", role="admin")

    mgr_login = await _login(client, tenant_code=tenant.code, username=manager.username, password="password123")
    mgr_key = mgr_login["api_key"]

    resp = await client.post(
        f"/api/auth/users/{admin.id}/password-reset",
        json={},
        headers={"X-API-Key": mgr_key},
    )
    assert resp.status_code == 403, resp.text
