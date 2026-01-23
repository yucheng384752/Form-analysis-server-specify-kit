import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.main import app
from app.models.core.schema_registry import TableRegistry
from app.models.core.tenant import Tenant
from app.models.import_job import ImportJob
from app.models.import_job import ImportJobStatus
from app.models.p1_record import P1Record
from app.services.import_v2 import ImportService


@pytest.fixture
async def client(db_session_clean):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_import_job_from_upload_job_and_commit(client, db_session_clean):
    tenant = Tenant(name="T1", code=f"t1_{uuid.uuid4()}", is_default=True, is_active=True)
    db_session_clean.add(tenant)
    await db_session_clean.commit()

    db_session_clean.add(TableRegistry(table_code="P1", display_name="P1"))
    await db_session_clean.commit()

    # 1) create UploadJob by uploading CSV (user can edit later; v2 job uses stored bytes)
    upload_resp = await client.post(
        "/api/upload",
        headers={"X-Tenant-Id": str(tenant.id)},
        files={"file": ("P1_2503033_01.csv", b"lot_no,quantity\n2503033_01,1\n", "text/csv")},
    )
    assert upload_resp.status_code == 200, upload_resp.text
    upload_process_id = uuid.UUID(str(upload_resp.json()["process_id"]))

    # 2) create v2 import job from upload job
    create_resp = await client.post(
        "/api/v2/import/jobs/from-upload-job",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"upload_process_id": str(upload_process_id)},
    )
    assert create_resp.status_code == 201, create_resp.text
    job_id = uuid.UUID(str(create_resp.json()["id"]))

    # Parse + validate synchronously (tests don't run background tasks)
    service = ImportService(db_session_clean)
    await service.parse_job(job_id, actor_kind="user")
    await service.validate_job(job_id, actor_kind="user")

    # 3) commit via API (testing env commits synchronously)
    commit_resp = await client.post(
        f"/api/v2/import/jobs/{job_id}/commit",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert commit_resp.status_code == 200, commit_resp.text

    # Ensure job exists
    job = (
        await db_session_clean.execute(select(ImportJob).where(ImportJob.id == job_id, ImportJob.tenant_id == tenant.id))
    ).scalar_one()
    assert job.status == ImportJobStatus.COMPLETED

    # Verify P1Record created
    rec = (
        await db_session_clean.execute(
            select(P1Record).where(P1Record.tenant_id == tenant.id, P1Record.lot_no_norm == 250303301)
        )
    ).scalar_one_or_none()
    assert rec is not None
