import base64
import io
import uuid
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.core.database as core_database
from app.core.config import get_settings
from app.models.core.tenant import Tenant
from app.models.pdf_conversion_job import PdfConversionJob, PdfConversionStatus
from app.models.pdf_upload import PdfUpload
from app.models.upload_job import JobStatus, UploadJob
from app.services import pdf_conversion


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _zip_base64_csvs(files: dict[str, str]) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.mark.asyncio
async def test_pdf_conversion_background_auto_ingests_into_upload_jobs(
    db_session_clean, test_engine, monkeypatch
):
    # Ensure the middleware/background code path can open sessions.
    previous_factory = core_database.async_session_factory
    core_database.async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Fake external PDF server response (ZIP -> 2 CSV files).
    async def fake_call_pdf_server_convert(
        *, pdf_bytes: bytes, filename: str, options=None
    ):
        assert pdf_bytes.startswith(b"%PDF-")
        return {
            "zip_base64": _zip_base64_csvs(
                {
                    "P1_2503033_01.csv": "lot_no,quantity\n2503033_01,1\n",
                    "P2_2503033_01.csv": "lot_no,quantity\n2503033_01,2\n",
                }
            )
        }

    monkeypatch.setattr(
        pdf_conversion, "_call_pdf_server_convert", fake_call_pdf_server_convert
    )

    settings = get_settings()
    base_dir = Path(settings.upload_temp_dir)

    # Create tenant + pdf upload record and write PDF to disk where the background task expects.
    tenant = Tenant(
        name="T1", code=f"t1_{uuid.uuid4()}", is_default=True, is_active=True
    )
    db_session_clean.add(tenant)
    await db_session_clean.commit()
    await db_session_clean.refresh(tenant)

    process_id = uuid.uuid4()
    pdf_dir = base_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{process_id}.pdf"
    pdf_path.write_bytes(_pdf_bytes())

    upload = PdfUpload(
        process_id=process_id,
        tenant_id=tenant.id,
        filename="sample.pdf",
        file_size=len(_pdf_bytes()),
        storage_path=str(pdf_path),
    )
    db_session_clean.add(upload)

    job = PdfConversionJob(
        process_id=process_id,
        tenant_id=tenant.id,
        status=PdfConversionStatus.QUEUED,
        progress=0,
    )
    db_session_clean.add(job)
    await db_session_clean.commit()
    await db_session_clean.refresh(job)

    # Run background conversion (should also auto-ingest).
    await pdf_conversion.process_pdf_conversion_job_background(job.id)

    # Verify conversion job completed and recorded outputs.
    # Background task runs in a separate session, so refresh to avoid identity-map staleness.
    await db_session_clean.refresh(job)
    assert job.status == PdfConversionStatus.COMPLETED
    assert isinstance(job.output_paths, list)
    assert len(job.output_paths) == 2
    assert isinstance(job.ingested_upload_jobs, list)
    assert len(job.ingested_upload_jobs) == 2

    # Verify UploadJobs created.
    jobs = (
        (
            await db_session_clean.execute(
                select(UploadJob).where(UploadJob.tenant_id == tenant.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(jobs) == 2
    assert sorted([j.filename for j in jobs]) == [
        "P1_2503033_01.csv",
        "P2_2503033_01.csv",
    ]
    assert all(j.status == JobStatus.PENDING for j in jobs)
    assert all(j.total_rows is None for j in jobs)

    # Cleanup disk artifacts (best-effort).
    try:
        pdf_path.unlink(missing_ok=True)
    except TypeError:
        if pdf_path.exists():
            pdf_path.unlink()

    out_dir = base_dir / "pdf" / str(process_id)
    if out_dir.exists():
        for p in out_dir.glob("*.csv"):
            try:
                p.unlink(missing_ok=True)
            except TypeError:
                if p.exists():
                    p.unlink()
        try:
            out_dir.rmdir()
        except OSError:
            pass

    core_database.async_session_factory = previous_factory
