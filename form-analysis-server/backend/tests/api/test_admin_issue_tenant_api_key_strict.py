import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.api.deps import get_db
from app.main import app
from app.models.core.tenant import Tenant


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
        "admin_api_keys_str": getattr(settings, "admin_api_keys_str", None),
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


@pytest.mark.asyncio
async def test_admin_can_issue_tenant_api_key_and_use_it(client, db_session_clean):
    t1 = await _create_tenant(db_session_clean, code="t1")

    from app.main import settings

    settings.auth_mode = "api_key"
    settings.auth_api_key_header = "X-API-Key"
    settings.admin_api_keys_str = "test-admin-key"

    # 1) Issue a tenant API key using admin key only.
    issue = await client.post(
        "/api/auth/admin/tenant-api-keys",
        json={"tenant_id": str(t1.id)},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert issue.status_code == 200, issue.text
    body = issue.json()
    raw_key = str(body.get("api_key") or "").strip()
    assert raw_key

    # 2) Use the issued key to call a tenant-scoped API.
    resp = await client.get("/api/constants/materials", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)
