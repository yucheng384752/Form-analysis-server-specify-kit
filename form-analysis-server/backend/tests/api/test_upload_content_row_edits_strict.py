import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import get_db
from app.core import database as core_database
from app.core.auth import hash_api_key
from app.main import app, settings
from app.models import RowEdit
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey
from app.models.upload_job import UploadJob


@pytest.fixture
async def client_upload_content_edits(db_session_clean, test_engine):
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

    raw_key = "test-upload-content-edit-key"
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)
    api_key = TenantApiKey(
        tenant_id=tenant_id,
        key_hash=key_hash,
        label="uploader",
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
async def test_update_upload_content_writes_row_edits_and_lists(
    client_upload_content_edits, db_session_clean
):
    client, raw_key, tenant_id = client_upload_content_edits

    # 1) create upload job
    resp = await client.post(
        "/api/upload",
        headers={"X-API-Key": raw_key},
        files={"file": ("P1_1234567_01.csv", b"lot_no\n1234567_01\n", "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    process_id = uuid.UUID(str(resp.json()["process_id"]))

    job = (
        await db_session_clean.execute(
            select(UploadJob).where(UploadJob.process_id == process_id)
        )
    ).scalar_one()

    # 2) update content
    resp_put = await client.put(
        f"/api/upload/{process_id}/content",
        headers={"X-API-Key": raw_key},
        json={
            "csv_text": "a\n2\n",
            "reason_text": "fix upload csv",
        },
    )
    assert resp_put.status_code == 200, resp_put.text

    # 3) row_edits persisted
    row_edit = (
        (
            await db_session_clean.execute(
                select(RowEdit)
                .where(
                    RowEdit.tenant_id == tenant_id,
                    RowEdit.table_code == "UPLOAD",
                    RowEdit.record_id == job.id,
                )
                .order_by(RowEdit.created_at.desc())
            )
        )
        .scalars()
        .first()
    )

    assert row_edit is not None
    assert row_edit.created_by == "uploader"
    assert row_edit.reason_text == "fix upload csv"
    assert (row_edit.before_json or {}).get("process_id") == str(process_id)
    assert (row_edit.after_json or {}).get("process_id") == str(process_id)
    assert (row_edit.before_json or {}).get("file_sha256") != (
        row_edit.after_json or {}
    ).get("file_sha256")

    # 4) list endpoint
    resp_list = await client.get(
        f"/api/upload/{process_id}/edits",
        headers={"X-API-Key": raw_key},
    )
    assert resp_list.status_code == 200, resp_list.text
    edits = resp_list.json()
    assert isinstance(edits, list)
    assert edits, "Expected at least one edit entry"
    assert edits[0]["table_code"] == "UPLOAD"
    assert edits[0]["record_id"] == str(job.id)
