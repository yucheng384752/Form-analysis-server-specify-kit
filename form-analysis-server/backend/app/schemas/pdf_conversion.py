import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.upload import UploadErrorResponse


class PdfConversionStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    QUEUED = "QUEUED"
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PdfConvertTriggerResponse(BaseModel):
    job_id: uuid.UUID
    status: PdfConversionStatus


class PdfConvertStatusResponse(BaseModel):
    status: PdfConversionStatus
    job_id: uuid.UUID | None = None
    progress: int = Field(default=0, ge=0, le=100)
    external_job_id: str | None = None
    output_path: str | None = None
    output_paths: list[str] | None = None
    error_summary: dict[str, Any] | None = None


class PdfConvertIngestedUpload(BaseModel):
    filename: str
    process_id: uuid.UUID
    # Optional v2 import job created from this UploadJob.
    import_job_id: uuid.UUID | None = None
    total_rows: int
    valid_rows: int
    invalid_rows: int
    sample_errors: list[UploadErrorResponse] = Field(default=[])
    csv_text: str | None = None


class PdfConvertIngestResponse(BaseModel):
    uploads: list[PdfConvertIngestedUpload]


class PdfConvertOutputFile(BaseModel):
    filename: str
    csv_text: str | None = None


class PdfConvertOutputsResponse(BaseModel):
    outputs: list[PdfConvertOutputFile]
