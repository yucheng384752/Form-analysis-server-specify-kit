import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.api.deps import get_db
from app.core.auth import hash_api_key
from app.main import app
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey


@pytest.fixture(autouse=True)
def _restore_global_auth_settings():
    """These tests mutate the global `settings` object in `app.main`.

    Restore it after each test to avoid leaking auth mode into other test files.
    """
    from app.main import settings

    previous = {
        "auth_mode": getattr(settings, "auth_mode", None),
        "auth_api_key_header": getattr(settings, "auth_api_key_header", None),
        "auth_protect_prefixes_str": getattr(settings, "auth_protect_prefixes_str", None),
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

    # The API-key auth middleware uses app.core.database.async_session_factory,
    # which is normally initialized by FastAPI lifespan. In tests we set it
    # explicitly so middleware can query the DB.
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


async def _create_tenant(db_session_clean, *, code: str, is_default: bool) -> Tenant:
    tenant = Tenant(
        name=f"Test Tenant {code} {uuid.uuid4()}",
        code=code,
        is_default=is_default,
        is_active=True,
    )
    db_session_clean.add(tenant)
    await db_session_clean.commit()
    await db_session_clean.refresh(tenant)
    return tenant


@pytest.mark.asyncio
async def test_auth_off_multiple_tenants_requires_header(client, db_session_clean):
    # Two tenants, no default -> legacy behavior requires explicit X-Tenant-Id.
    await _create_tenant(db_session_clean, code="t1", is_default=False)
    await _create_tenant(db_session_clean, code="t2", is_default=False)

    from app.main import settings

    settings.auth_mode = "off"

    resp = await client.get("/api/constants/materials")
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_auth_api_key_allows_call_without_tenant_header(client, db_session_clean):
    t1 = await _create_tenant(db_session_clean, code="t1", is_default=False)
    await _create_tenant(db_session_clean, code="t2", is_default=False)

    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"

    raw_key = "test-key-123"
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    db_session_clean.add(TenantApiKey(tenant_id=t1.id, key_hash=key_hash, label="test", is_active=True))
    await db_session_clean.commit()

    resp = await client.get("/api/constants/materials", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_auth_api_key_missing_or_wrong_key_is_401(client, db_session_clean):
    t1 = await _create_tenant(db_session_clean, code="t1", is_default=True)

    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"

    raw_key = "correct-key"
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    db_session_clean.add(TenantApiKey(tenant_id=t1.id, key_hash=key_hash, label="test", is_active=True))
    await db_session_clean.commit()

    resp_missing = await client.get("/api/tenants")
    assert resp_missing.status_code == 401, resp_missing.text

    resp_wrong = await client.get("/api/tenants", headers={"X-API-Key": "wrong-key"})
    assert resp_wrong.status_code == 401, resp_wrong.text


@pytest.mark.asyncio
async def test_auth_api_key_revoked_is_401(client, db_session_clean):
    t1 = await _create_tenant(db_session_clean, code="t1", is_default=True)

    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"

    raw_key = "revoked-key"
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    db_session_clean.add(TenantApiKey(tenant_id=t1.id, key_hash=key_hash, label="revoked", is_active=False))
    await db_session_clean.commit()

    resp = await client.get("/api/tenants", headers={"X-API-Key": raw_key})
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_auth_api_key_does_not_allow_tenant_switch_via_header(client, db_session_clean):
    # When auth is enabled, tenant is bound to key. Even if client sends X-Tenant-Id,
    # resolver should follow auth tenant.
    t1 = await _create_tenant(db_session_clean, code="t1", is_default=False)
    t2 = await _create_tenant(db_session_clean, code="t2", is_default=False)

    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"

    raw_key = "bound-key"
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    db_session_clean.add(TenantApiKey(tenant_id=t1.id, key_hash=key_hash, label="bound", is_active=True))
    await db_session_clean.commit()

    # This endpoint requires tenant dependency; without auth it would be 422.
    # With auth + mismatched X-Tenant-Id it should still succeed.
    resp = await client.get(
        "/api/constants/materials",
        headers={"X-API-Key": raw_key, "X-Tenant-Id": str(t2.id)},
    )
    assert resp.status_code == 200, resp.text

    # Sanity: key is bound to t1 (stored in DB)
    stored = (await db_session_clean.execute(select(TenantApiKey))).scalars().one()
    assert stored.tenant_id == t1.id
