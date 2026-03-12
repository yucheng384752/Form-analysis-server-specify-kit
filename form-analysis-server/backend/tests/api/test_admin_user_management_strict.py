import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_db
from app.core.auth import hash_api_key
from app.core.password import hash_password
from app.main import app
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey
from app.models.core.tenant_user import TenantUser


@pytest.fixture(autouse=True)
def _restore_global_settings():
    from app.main import settings

    previous = {
        "auth_mode": getattr(settings, "auth_mode", None),
        "auth_api_key_header": getattr(settings, "auth_api_key_header", None),
        "auth_protect_prefixes_str": getattr(
            settings, "auth_protect_prefixes_str", None
        ),
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

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    database.async_session_factory = previous_factory


async def _create_tenant(db_session_clean, *, code: str) -> Tenant:
    tenant = Tenant(
        name=f"Test Tenant {code} {uuid.uuid4()}",
        code=code,
        is_default=False,
        is_active=True,
    )
    db_session_clean.add(tenant)
    await db_session_clean.commit()
    await db_session_clean.refresh(tenant)
    return tenant


async def _create_user(
    db_session_clean, *, tenant_id, username: str, role: str
) -> TenantUser:
    user = TenantUser(
        tenant_id=tenant_id,
        username=username,
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db_session_clean.add(user)
    await db_session_clean.commit()
    await db_session_clean.refresh(user)
    return user


async def _create_api_key(
    db_session_clean, *, tenant_id, user_id, raw_key: str, label: str = "test"
) -> None:
    from app.main import settings

    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    db_session_clean.add(
        TenantApiKey(
            tenant_id=tenant_id,
            key_hash=key_hash,
            label=label,
            is_active=True,
            user_id=user_id,
        )
    )
    await db_session_clean.commit()


@pytest.mark.asyncio
async def test_admin_key_can_patch_tenant_without_x_api_key_when_auth_mode_api_key(
    client, db_session_clean
):
    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"
    settings.admin_api_keys_str = "test-admin-key"

    t1 = await _create_tenant(db_session_clean, code="t1")

    resp = await client.patch(
        f"/api/tenants/{t1.id}",
        json={"is_active": False},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(t1.id)
    assert body["is_active"] is False


@pytest.mark.asyncio
async def test_admin_key_can_patch_user_without_x_api_key_when_auth_mode_api_key(
    client, db_session_clean
):
    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"
    settings.admin_api_keys_str = "test-admin-key"

    t1 = await _create_tenant(db_session_clean, code="t1")
    u1 = await _create_user(
        db_session_clean, tenant_id=t1.id, username="u1", role="user"
    )

    resp = await client.patch(
        f"/api/auth/users/{u1.id}",
        json={"role": "manager"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(u1.id)
    assert body["role"] == "manager"


@pytest.mark.asyncio
async def test_create_user_rejects_admin_role(client, db_session_clean):
    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"
    settings.admin_api_keys_str = "test-admin-key"

    await _create_tenant(db_session_clean, code="t1")

    resp = await client.post(
        "/api/auth/users",
        json={
            "tenant_code": "t1",
            "username": "bad",
            "password": "password123",
            "role": "admin",
        },
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_tenant_manager_scoped_to_own_tenant_for_user_management(
    client, db_session_clean
):
    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"

    t1 = await _create_tenant(db_session_clean, code="t1")
    t2 = await _create_tenant(db_session_clean, code="t2")

    manager_user_t1 = await _create_user(
        db_session_clean, tenant_id=t1.id, username="manager1", role="manager"
    )
    other_user_t2 = await _create_user(
        db_session_clean, tenant_id=t2.id, username="user2", role="user"
    )

    raw_key = "tenant1-manager-key"
    await _create_api_key(
        db_session_clean, tenant_id=t1.id, user_id=manager_user_t1.id, raw_key=raw_key
    )

    # List should only include tenant t1.
    list_resp = await client.get("/api/auth/users", headers={"X-API-Key": raw_key})
    assert list_resp.status_code == 200, list_resp.text
    users = list_resp.json()
    assert isinstance(users, list)
    assert any(u["id"] == str(manager_user_t1.id) for u in users)
    assert all(u["tenant_id"] == str(t1.id) for u in users)

    # Cross-tenant update must be forbidden.
    patch_resp = await client.patch(
        f"/api/auth/users/{other_user_t2.id}",
        json={"is_active": False},
        headers={"X-API-Key": raw_key},
    )
    assert patch_resp.status_code == 403, patch_resp.text

    # Sanity: t2 user still active.
    stored = (
        await db_session_clean.execute(
            select(TenantUser).where(TenantUser.id == other_user_t2.id)
        )
    ).scalar_one()
    assert bool(stored.is_active) is True
