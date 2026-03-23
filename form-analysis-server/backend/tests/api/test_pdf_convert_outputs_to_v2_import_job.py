import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.core.config import get_settings
from app.main import app
from app.models.core.schema_registry import TableRegistry
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.pdf_conversion_job import PdfConversionJob, PdfConversionStatus
from app.services.import_v2 import ImportService


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
async def test_pdf_convert_outputs_can_flow_into_v2_import_job_commit(
    client, db_session_clean
):
    # Seed tenant
    tenant = Tenant(name="T1", code="t1", is_default=True, is_active=True)
    db_session_clean.add(tenant)
    await db_session_clean.commit()

    # Seed table registry for v2 import jobs
    db_session_clean.add(TableRegistry(table_code="P1", display_name="P1"))
    await db_session_clean.commit()

    # Upload a PDF
    files = {"file": ("sample.pdf", _pdf_bytes(), "application/pdf")}
    upload_resp = await client.post(
        "/api/upload/pdf", files=files, headers={"X-Tenant-Id": str(tenant.id)}
    )
    assert upload_resp.status_code == 200, upload_resp.text
    pdf_process_id = uuid.UUID(str(upload_resp.json()["process_id"]))

    # Fake converter outputs
    settings = get_settings()
    out_dir = Path(settings.upload_temp_dir) / "pdf" / str(pdf_process_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv1 = out_dir / "P1_2503033_01.csv"
    csv1.write_text("lot_no,quantity\n2503033_01,1\n", encoding="utf-8")

    job = PdfConversionJob(
        process_id=pdf_process_id,
        tenant_id=tenant.id,
        status=PdfConversionStatus.COMPLETED,
        progress=100,
        output_path=str(csv1),
        output_paths=[str(csv1)],
    )
    db_session_clean.add(job)
    await db_session_clean.commit()

    # 1) Get outputs (csv_text)
    outputs_resp = await client.get(
        f"/api/upload/pdf/{pdf_process_id}/convert/outputs?include_csv_text=1",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert outputs_resp.status_code == 200, outputs_resp.text
    outputs = outputs_resp.json().get("outputs")
    assert isinstance(outputs, list)
    assert len(outputs) == 1
    assert outputs[0]["filename"].startswith("P1_")
    csv_text = outputs[0].get("csv_text")
    assert isinstance(csv_text, str)

    # 2) Create v2 import job from output
    form = {
        "table_code": "P1",
        "allow_duplicate": "true",
    }
    multipart_files = [
        ("files", (outputs[0]["filename"], csv_text.encode("utf-8"), "text/csv")),
    ]

    create_job_resp = await client.post(
        "/api/v2/import/jobs",
        data=form,
        files=multipart_files,
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert create_job_resp.status_code == 201, create_job_resp.text
    job_id = uuid.UUID(str(create_job_resp.json()["id"]))

    # Parse + validate synchronously (tests don't run background tasks)
    service = ImportService(db_session_clean)
    await service.parse_job(job_id, actor_kind="user")
    await service.validate_job(job_id, actor_kind="user")

    # 3) Commit via API (in testing env commit runs synchronously)
    commit_resp = await client.post(
        f"/api/v2/import/jobs/{job_id}/commit",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert commit_resp.status_code == 200, commit_resp.text

    # Verify P1Record created
    result = await db_session_clean.execute(
        select(P1Record).where(
            P1Record.tenant_id == tenant.id, P1Record.lot_no_norm == 250303301
        )
    )
    record = result.scalar_one_or_none()
    assert record is not None
    assert isinstance(getattr(record, "extras", None), dict)

    # Cleanup disk files
    pdf_path = Path(settings.upload_temp_dir) / "pdf" / f"{pdf_process_id}.pdf"
    try:
        pdf_path.unlink(missing_ok=True)
    except TypeError:
        if pdf_path.exists():
            pdf_path.unlink()

    try:
        csv1.unlink(missing_ok=True)
    except TypeError:
        if csv1.exists():
            csv1.unlink()

    try:
        out_dir.rmdir()
    except OSError:
        pass
