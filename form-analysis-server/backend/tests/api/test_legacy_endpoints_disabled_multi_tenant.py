import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.api.deps import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _restore_global_multi_tenant_setting():
    """Restore the global `settings` object in `app.main` after each test."""
    from app.main import settings

    previous = getattr(settings, "multi_tenant_enabled", False)
    yield
    settings.multi_tenant_enabled = previous


@pytest.fixture
async def client(db_session_clean, test_engine):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    from app.main import settings

    prev_admin_keys = getattr(settings, "admin_api_keys_str", "")
    settings.admin_api_keys_str = "test-admin-key"

    # Some middleware/background tasks rely on the global async session factory.
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
    settings.admin_api_keys_str = prev_admin_keys


@pytest.fixture
async def tenant_id(client):
    create = await client.post(
        "/api/tenants",
        json={},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert create.status_code == 201, create.text
    return create.json()["id"]


@pytest.mark.asyncio
async def test_multi_tenant_rejects_legacy_import(client, tenant_id):
    from app.main import settings

    settings.multi_tenant_enabled = True

    resp = await client.post(
        "/api/import",
        json={"process_id": str(uuid.uuid4())},
        headers={"X-Tenant-Id": str(tenant_id)},
    )

    assert resp.status_code == 410, resp.text
    body = resp.json()
    assert body["detail"]["error_code"] == "LEGACY_IMPORT_DISABLED"


@pytest.mark.asyncio
async def test_multi_tenant_rejects_legacy_errors_csv(client, tenant_id):
    from app.main import settings

    settings.multi_tenant_enabled = True

    resp = await client.get(
        f"/api/errors.csv?process_id={uuid.uuid4()}",
        headers={"X-Tenant-Id": str(tenant_id)},
    )

    assert resp.status_code == 410, resp.text
    body = resp.json()
    assert body["detail"]["error_code"] == "LEGACY_EXPORT_DISABLED"


@pytest.mark.asyncio
async def test_multi_tenant_rejects_legacy_upload(client, tenant_id):
    from app.main import settings

    settings.multi_tenant_enabled = True

    resp = await client.post(
        "/api/upload",
        files={
            "file": (
                "P1_2507173_02.csv",
                b"LOT NO.\n2507173_02\n",
                "text/csv",
            )
        },
        headers={"X-Tenant-Id": str(tenant_id)},
    )

    assert resp.status_code == 410, resp.text
    body = resp.json()
    assert body["detail"]["error_code"] == "LEGACY_UPLOAD_DISABLED"
