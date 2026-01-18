from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from sqlalchemy import select

from app.core import database
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.pdf_conversion_job import PdfConversionJob, PdfConversionStatus
from app.models.pdf_upload import PdfUpload

logger = get_logger(__name__)


class PdfServerNotConfigured(RuntimeError):
    pass


def _to_error_summary(error: Exception | str, *, stage: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "error": str(error),
    }


async def _call_pdf_server_convert(
    *,
    pdf_bytes: bytes,
    filename: str,
    options: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    settings = get_settings()
    base_url = (getattr(settings, "pdf_server_url", None) or "").strip()
    if not base_url:
        raise PdfServerNotConfigured("PDF_SERVER_URL is not configured")

    convert_path = (getattr(settings, "pdf_server_convert_path", None) or "/convert").strip() or "/convert"
    url = base_url.rstrip("/") + (convert_path if convert_path.startswith("/") else ("/" + convert_path))

    timeout_seconds = int(getattr(settings, "pdf_server_timeout_seconds", 60))

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        files = {"file": (filename, pdf_bytes, "application/pdf")}
        data = {}
        if options:
            # Send options as JSON string field to be flexible.
            import json

            data["options"] = json.dumps(options, ensure_ascii=False)
        resp = await client.post(url, files=files, data=data)
        resp.raise_for_status()
        return resp.json()


def _extract_csv_text(result: dict[str, Any]) -> str:
    if isinstance(result.get("csv_text"), str) and result["csv_text"].strip():
        return result["csv_text"]
    if isinstance(result.get("csv"), str) and result["csv"].strip():
        return result["csv"]

    b64 = result.get("csv_base64")
    if isinstance(b64, str) and b64.strip():
        return base64.b64decode(b64).decode("utf-8", errors="replace")

    raise ValueError("PDF server response does not contain csv_text/csv/csv_base64")


async def process_pdf_conversion_job_background(job_id: uuid.UUID) -> None:
    if not database.async_session_factory:
        logger.error("Async session factory not initialized; cannot process pdf conversion job", job_id=str(job_id))
        return

    settings = get_settings()

    async with database.async_session_factory() as db:
        stmt = select(PdfConversionJob).where(PdfConversionJob.id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            return

        # Load upload record
        upload = (await db.execute(select(PdfUpload).where(PdfUpload.process_id == job.process_id))).scalar_one_or_none()
        if not upload:
            job.status = PdfConversionStatus.FAILED
            job.progress = 100
            job.error_summary = _to_error_summary("PDF upload record not found", stage="load_upload")
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            return

        try:
            job.status = PdfConversionStatus.UPLOADING
            job.progress = 15
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

            pdf_path = Path(upload.storage_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")

            pdf_bytes = pdf_path.read_bytes()

            job.status = PdfConversionStatus.PROCESSING
            job.progress = 45
            await db.commit()

            # Call external server
            result = await _call_pdf_server_convert(
                pdf_bytes=pdf_bytes,
                filename=upload.filename,
                options={
                    "output_format": "csv",
                },
            )

            csv_text = _extract_csv_text(result)

            out_dir = Path(settings.upload_temp_dir) / "pdf"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{upload.process_id}.csv"
            out_path.write_text(csv_text, encoding="utf-8")

            job.status = PdfConversionStatus.COMPLETED
            job.progress = 100
            job.output_path = str(out_path)
            job.finished_at = datetime.now(timezone.utc)
            job.error_summary = None
            await db.commit()

        except PdfServerNotConfigured as e:
            job.status = PdfConversionStatus.FAILED
            job.progress = 100
            job.error_summary = _to_error_summary(e, stage="config")
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            logger.exception("PDF conversion job failed", job_id=str(job_id), process_id=str(job.process_id))
            job.status = PdfConversionStatus.FAILED
            job.progress = 100
            job.error_summary = _to_error_summary(e, stage="convert")
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
