import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import get_db
from app.core import database as core_database
from app.core.auth import hash_api_key
from app.main import app, settings
from app.models.core.audit_event import AuditEvent
from app.models.core.schema_registry import TableRegistry
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey
from app.models.p1_record import P1Record
from app.utils.normalization import normalize_lot_no


@pytest.fixture
async def client_obs_audit_enabled(db_session_clean, test_engine):
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
    prev_audit_enabled = settings.audit_events_enabled
    prev_admin_keys = getattr(settings, "admin_api_keys_str", "")
    settings.auth_mode = "api_key"
    settings.audit_events_enabled = True
    settings.admin_api_keys_str = "test-admin-key"

    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        name="UT",
        code="ut",
        is_active=True,
        is_default=True,
    )
    db_session_clean.add(tenant)

    raw_key = "test-obs-audit-key"
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    api_key = TenantApiKey(
        tenant_id=tenant_id,
        key_hash=key_hash,
        label="test-key",
        is_active=True,
    )
    db_session_clean.add(api_key)

    # Ensure TableRegistry exists for import v2.
    p1_table = (
        await db_session_clean.execute(
            select(TableRegistry).where(TableRegistry.table_code == "P1")
        )
    ).scalar_one_or_none()
    if not p1_table:
        p1_table = TableRegistry(table_code="P1", display_name="P1 Records")
        db_session_clean.add(p1_table)

    await db_session_clean.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac, raw_key, tenant_id, api_key.id

    app.dependency_overrides.clear()
    settings.auth_mode = prev_auth_mode
    settings.audit_events_enabled = prev_audit_enabled
    settings.admin_api_keys_str = prev_admin_keys
    core_database.engine = prev_engine
    core_database.async_session_factory = prev_factory


@pytest.mark.asyncio
async def test_obs_audit_trail_import_query_edit(
    client_obs_audit_enabled, db_session_clean
):
    client, raw_key, tenant_id, api_key_id = client_obs_audit_enabled

    # 1) Create import job
    files = [("files", ("P1_2503033_01.csv", b"col1,col2\nval1,val2\n", "text/csv"))]
    data = {"table_code": "P1"}

    resp = await client.post(
        "/api/v2/import/jobs",
        files=files,
        data=data,
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 201, resp.text
    job_id = uuid.UUID(resp.json()["id"])

    # Semantic create event
    created = (
        (
            await db_session_clean.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "import.job.create",
                    AuditEvent.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert created, "Expected import.job.create audit event"

    # 2) Parse + validate happen in background (system).
    # Commit via endpoint (testing env commits synchronously).
    resp_commit = await client.post(
        f"/api/v2/import/jobs/{job_id}/commit",
        headers={"X-API-Key": raw_key},
    )
    assert resp_commit.status_code == 200, resp_commit.text

    status_events = (
        (
            await db_session_clean.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "import.job.status",
                    AuditEvent.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert any(
        (e.metadata_json or {}).get("job_id") == str(job_id) for e in status_events
    )
    assert any(
        (e.metadata_json or {}).get("to_status") == "READY" for e in status_events
    )
    assert any(
        (e.metadata_json or {}).get("to_status") == "COMPLETED" for e in status_events
    )

    # 3) Advanced query (GET) should write semantic audit event when filters provided
    resp_q = await client.get(
        "/api/v2/query/records/advanced",
        params={"specification": "PE32"},
        headers={"X-API-Key": raw_key},
    )
    assert resp_q.status_code == 200, resp_q.text

    query_events = (
        (
            await db_session_clean.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "query.advanced",
                    AuditEvent.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert query_events, "Expected query.advanced audit event"

    # 4) Edit record should write semantic audit event
    record_id = uuid.uuid4()
    rec = P1Record(
        id=record_id,
        tenant_id=tenant_id,
        lot_no_raw="2503033_02",
        lot_no_norm=normalize_lot_no("2503033_02"),
        extras={"rows": []},
    )
    db_session_clean.add(rec)
    await db_session_clean.commit()

    resp_edit = await client.patch(
        f"/api/edit/records/P1/{record_id}",
        json={"updates": {"lot_no_raw": "2503033_02"}, "reason_text": "fix"},
        headers={"X-API-Key": raw_key},
    )
    assert resp_edit.status_code == 200, resp_edit.text

    edit_events = (
        (
            await db_session_clean.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "edit.record",
                    AuditEvent.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert any(
        (e.metadata_json or {}).get("record_id") == str(record_id) for e in edit_events
    )

    # 5) Audit event listing endpoints
    resp_list = await client.get("/api/audit-events", headers={"X-API-Key": raw_key})
    assert resp_list.status_code == 200, resp_list.text

    resp_admin_list = await client.get(
        "/api/admin/audit-events",
        headers={"X-API-Key": raw_key, "X-Admin-API-Key": "test-admin-key"},
    )
    assert resp_admin_list.status_code == 200, resp_admin_list.text
