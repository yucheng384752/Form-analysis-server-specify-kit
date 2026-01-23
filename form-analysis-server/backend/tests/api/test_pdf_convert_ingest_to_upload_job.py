import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.core.config import get_settings
from app.main import app
from app.models.core.tenant import Tenant
from app.models.core.schema_registry import TableRegistry
from app.models.pdf_conversion_job import PdfConversionJob, PdfConversionStatus


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@pytest.fixture
async def client(db_session_clean):
    async def override_get_db():
        yield db_session_clean

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pdf_convert_ingest_creates_upload_jobs_and_is_idempotent(client, db_session_clean):
    tenant = Tenant(name="T1", code="t1", is_default=True, is_active=True)
    db_session_clean.add(tenant)
    await db_session_clean.commit()

    # Seed table registry for v2 import jobs created during ingest
    db_session_clean.add_all([
        TableRegistry(table_code="P1", display_name="P1"),
        TableRegistry(table_code="P2", display_name="P2"),
    ])
    await db_session_clean.commit()

    files = {"file": ("sample.pdf", _pdf_bytes(), "application/pdf")}
    upload_resp = await client.post("/api/upload/pdf", files=files, headers={"X-Tenant-Id": str(tenant.id)})
    assert upload_resp.status_code == 200, upload_resp.text
    pdf_process_id = uuid.UUID(str(upload_resp.json()["process_id"]))

    settings = get_settings()
    out_dir = Path(settings.upload_temp_dir) / "pdf" / str(pdf_process_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv1 = out_dir / "P1_2503033_01.csv"
    csv2 = out_dir / "P2_2503033_01.csv"
    csv1.write_text("lot_no,quantity\n2503033_01,1\n", encoding="utf-8")
    csv2.write_text("lot_no,quantity\n2503033_01,2\n", encoding="utf-8")

    job = PdfConversionJob(
        process_id=pdf_process_id,
        tenant_id=tenant.id,
        status=PdfConversionStatus.COMPLETED,
        progress=100,
        output_path=str(csv1),
        output_paths=[str(csv1), str(csv2)],
    )
    db_session_clean.add(job)
    await db_session_clean.commit()

    ingest_resp = await client.post(
        f"/api/upload/pdf/{pdf_process_id}/convert/ingest?include_csv_text=1",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert ingest_resp.status_code == 200, ingest_resp.text
    body = ingest_resp.json()
    uploads = body.get("uploads")
    assert isinstance(uploads, list)
    assert len(uploads) == 2

    process_ids = [u["process_id"] for u in uploads]
    assert len(set(process_ids)) == 2
    for u in uploads:
        assert u.get("filename")
        assert isinstance(u.get("csv_text"), str)
        assert u.get("import_job_id"), "ingest should also create v2 import jobs"

        # Import job should be queryable
        job_resp = await client.get(
            f"/api/v2/import/jobs/{u['import_job_id']}",
            headers={"X-Tenant-Id": str(tenant.id)},
        )
        assert job_resp.status_code == 200, job_resp.text

        status_resp = await client.get(
            f"/api/upload/{u['process_id']}/status",
            headers={"X-Tenant-Id": str(tenant.id)},
        )
        assert status_resp.status_code == 200, status_resp.text

    # Idempotent second call returns same upload jobs
    ingest_resp2 = await client.post(
        f"/api/upload/pdf/{pdf_process_id}/convert/ingest?include_csv_text=1",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert ingest_resp2.status_code == 200, ingest_resp2.text
    body2 = ingest_resp2.json()
    uploads2 = body2.get("uploads")
    assert sorted([u["process_id"] for u in uploads2]) == sorted(process_ids)
    assert sorted([u["import_job_id"] for u in uploads2]) == sorted([u["import_job_id"] for u in uploads])

    # Cleanup disk files to keep workspace tidy
    pdf_path = Path(settings.upload_temp_dir) / "pdf" / f"{pdf_process_id}.pdf"
    try:
        pdf_path.unlink(missing_ok=True)
    except TypeError:
        if pdf_path.exists():
            pdf_path.unlink()

    for p in [csv1, csv2]:
        try:
            p.unlink(missing_ok=True)
        except TypeError:
            if p.exists():
                p.unlink()

    try:
        out_dir.rmdir()
    except OSError:
        # If not empty for any reason, leave it.
        pass
