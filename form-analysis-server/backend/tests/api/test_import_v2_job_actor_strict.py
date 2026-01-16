import shutil
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import get_db
from app.core import database as core_database
from app.core.auth import hash_api_key
from app.core.config import get_settings
from app.main import app, settings
from app.models.core.schema_registry import TableRegistry
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey
from app.models.import_job import ImportJob


@pytest.fixture
async def client_import_job_actor(db_session_clean, test_engine):
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

    table = TableRegistry(table_code="P1", display_name="P1 Records")
    db_session_clean.add(table)

    raw_key = "test-import-key"
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    api_key = TenantApiKey(
        tenant_id=tenant_id,
        key_hash=key_hash,
        label="importer",
        is_active=True,
    )
    db_session_clean.add(api_key)

    await db_session_clean.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, raw_key, tenant_id, api_key.id

    settings.auth_mode = prev_auth_mode
    core_database.engine = prev_engine
    core_database.async_session_factory = prev_factory
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_import_job_writes_actor_fields(client_import_job_actor, db_session_clean):
    client, raw_key, tenant_id, api_key_id = client_import_job_actor

    files = [
        ("files", ("P1_1234567_01.csv", b"a\n1\n", "text/csv")),
    ]

    resp = await client.post(
        "/api/v2/import/jobs",
        headers={"X-API-Key": raw_key},
        data={"table_code": "P1"},
        files=files,
    )
    assert resp.status_code == 201, resp.text

    job_id = uuid.UUID(resp.json()["id"])

    result = await db_session_clean.execute(select(ImportJob).where(ImportJob.id == job_id))
    job = result.scalar_one()

    assert job.tenant_id == tenant_id
    assert job.actor_api_key_id == api_key_id
    assert job.actor_label_snapshot == "importer"

    # Background parse/validate updates status and should be attributed to system.
    assert job.last_status_actor_kind == "system"
    assert job.last_status_actor_api_key_id is None
    assert job.last_status_actor_label_snapshot is None

    # Cleanup uploaded files
    settings_local = get_settings()
    upload_dir = Path(settings_local.upload_temp_dir) / str(job_id)
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
