import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import get_db
from app.core import database as core_database
from app.core.auth import hash_api_key
from app.main import app, settings
from app.models import EditReason
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey


@pytest.fixture
async def client_edit_reasons(db_session_clean, test_engine):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    prev_engine = core_database.engine
    prev_factory = core_database.async_session_factory
    core_database.engine = test_engine
    core_database.async_session_factory = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
    )

    prev_auth_mode = settings.auth_mode
    settings.auth_mode = "api_key"

    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        name="UT",
        code="ut",
        is_active=True,
        is_default=True,
    )
    db_session_clean.add(tenant)

    raw_key = "test-edit-reasons-key"
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    api_key = TenantApiKey(
        tenant_id=tenant_id,
        key_hash=key_hash,
        label="reason-admin",
        is_active=True,
    )
    db_session_clean.add(api_key)

    await db_session_clean.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, raw_key, tenant_id

    settings.auth_mode = prev_auth_mode
    core_database.engine = prev_engine
    core_database.async_session_factory = prev_factory
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_edit_reasons_crud_and_active_filter(
    client_edit_reasons, db_session_clean
):
    client, raw_key, tenant_id = client_edit_reasons

    # Create
    resp_create = await client.post(
        "/api/edit/reasons",
        headers={"X-API-Key": raw_key},
        json={
            "reason_code": "CUSTOM_FIX",
            "description": "Custom fix",
            "display_order": 10,
            "is_active": True,
        },
    )
    assert resp_create.status_code == 200, resp_create.text
    reason_id = uuid.UUID(resp_create.json()["id"])

    # Uniqueness
    resp_dup = await client.post(
        "/api/edit/reasons",
        headers={"X-API-Key": raw_key},
        json={
            "reason_code": "CUSTOM_FIX",
            "description": "Dup",
            "display_order": 11,
            "is_active": True,
        },
    )
    assert resp_dup.status_code == 409, resp_dup.text

    # Update (deactivate)
    resp_patch = await client.patch(
        f"/api/edit/reasons/{reason_id}",
        headers={"X-API-Key": raw_key},
        json={
            "description": "Custom fix (updated)",
            "is_active": False,
        },
    )
    assert resp_patch.status_code == 200, resp_patch.text

    # GET list only returns active
    resp_list = await client.get(
        "/api/edit/reasons",
        headers={"X-API-Key": raw_key},
    )
    assert resp_list.status_code == 200, resp_list.text
    assert resp_list.json() == []

    # DB still has it
    db_reason = (
        await db_session_clean.execute(
            select(EditReason).where(
                EditReason.id == reason_id, EditReason.tenant_id == tenant_id
            )
        )
    ).scalar_one()
    assert db_reason.is_active is False
