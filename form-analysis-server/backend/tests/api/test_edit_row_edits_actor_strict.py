import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import get_db
from app.core.auth import hash_api_key
from app.core import database as core_database
from app.main import app, settings
from app.models import P1Record, RowEdit
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey


@pytest.fixture
async def client_edit_actor(db_session_clean, test_engine):
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

    raw_key = "test-edit-key"
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    api_key = TenantApiKey(
        tenant_id=tenant_id,
        key_hash=key_hash,
        label="editor",
        is_active=True,
    )
    db_session_clean.add(api_key)

    record_id = uuid.uuid4()
    record = P1Record(
        id=record_id,
        tenant_id=tenant_id,
        lot_no_raw="1234567_01",
        lot_no_norm=123456701,
        extras={},
    )
    db_session_clean.add(record)

    await db_session_clean.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac, raw_key, tenant_id, record_id

    settings.auth_mode = prev_auth_mode
    core_database.engine = prev_engine
    core_database.async_session_factory = prev_factory
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_edit_route_writes_row_edits_created_by_actor(client_edit_actor, db_session_clean):
    client, raw_key, tenant_id, record_id = client_edit_actor

    resp = await client.patch(
        f"/api/edit/records/P1/{record_id}",
        headers={"X-API-Key": raw_key},
        json={
            # New (recommended) flat payload: no nested "request".
            # tenant_id is optional when AUTH_MODE=api_key binds a tenant.
            "updates": {"extras": {"note": "changed"}},
            "reason_id": None,
            "reason_text": "test",
        },
    )
    assert resp.status_code == 200, resp.text

    result = await db_session_clean.execute(
        select(RowEdit).where(RowEdit.record_id == record_id).order_by(RowEdit.created_at.desc())
    )
    row_edit = result.scalars().first()
    assert row_edit is not None
    assert row_edit.created_by == "editor"


@pytest.mark.asyncio
async def test_edit_route_accepts_legacy_nested_request_shape(client_edit_actor, db_session_clean):
    client, raw_key, tenant_id, record_id = client_edit_actor

    resp = await client.patch(
        f"/api/edit/records/P1/{record_id}",
        headers={"X-API-Key": raw_key},
        json={
            # Legacy shape: {tenant_id?, request:{...}}
            "request": {
                "updates": {"extras": {"note": "changed-legacy"}},
                "reason_id": None,
                "reason_text": "legacy",
            }
        },
    )
    assert resp.status_code == 200, resp.text

    result = await db_session_clean.execute(
        select(RowEdit).where(RowEdit.record_id == record_id).order_by(RowEdit.created_at.desc())
    )
    row_edit = result.scalars().first()
    assert row_edit is not None
    assert row_edit.created_by == "editor"
