import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import get_db
from app.core.auth import hash_api_key
from app.core import database as core_database
from app.main import app, settings
from app.models.core.audit_event import AuditEvent
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey


@pytest.fixture
async def client_audit_enabled(db_session_clean, test_engine):
    # 1) Override route DB dependency to use the per-test session.
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    # 2) Ensure middleware (api_key_auth_middleware / audit_events_middleware) can write to DB.
    prev_engine = core_database.engine
    prev_factory = core_database.async_session_factory
    core_database.engine = test_engine
    core_database.async_session_factory = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
    )

    # 3) Enable auth + audit (and restore afterwards).
    prev_auth_mode = settings.auth_mode
    prev_audit_enabled = settings.audit_events_enabled
    prev_admin_keys = getattr(settings, "admin_api_keys_str", "")
    settings.auth_mode = "api_key"
    settings.audit_events_enabled = True
    settings.admin_api_keys_str = "test-admin-key"

    # 4) Seed a tenant + API key so auth can succeed.
    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        name="UT",
        code="ut",
        is_active=True,
        is_default=True,
    )
    db_session_clean.add(tenant)

    raw_key = "test-audit-key"
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    api_key = TenantApiKey(
        tenant_id=tenant_id,
        key_hash=key_hash,
        label="test-key",
        is_active=True,
    )
    db_session_clean.add(api_key)
    await db_session_clean.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac, raw_key, tenant_id, api_key.id

    # Cleanup: restore global state.
    app.dependency_overrides.clear()
    settings.auth_mode = prev_auth_mode
    settings.audit_events_enabled = prev_audit_enabled
    settings.admin_api_keys_str = prev_admin_keys
    core_database.engine = prev_engine
    core_database.async_session_factory = prev_factory


@pytest.mark.asyncio
async def test_audit_events_enabled_persists_write_event(client_audit_enabled, db_session_clean):
    client, raw_key, tenant_id, api_key_id = client_audit_enabled

    # Tenant already exists; POST /api/tenants should be blocked with 409.
    # That's fine: we still expect an audit event to be written.
    resp = await client.post(
        "/api/tenants",
        json={},
        headers={"X-API-Key": raw_key, "X-Admin-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 409, resp.text

    request_id = resp.headers.get("X-Request-ID")
    assert request_id, "Expected X-Request-ID header"

    result = await db_session_clean.execute(
        select(AuditEvent).where(AuditEvent.request_id == request_id)
    )
    event = result.scalar_one_or_none()
    assert event is not None

    assert str(event.request_id) == str(request_id)
    assert str(event.tenant_id) == str(tenant_id)
    assert str(event.actor_api_key_id) == str(api_key_id)
    assert event.actor_label_snapshot == "test-key"
    assert event.method == "POST"
    assert event.path == "/api/tenants"
    assert event.status_code == 409
