import uuid
from enum import Enum
from typing import Any, Optional
from typing import List

from app.schemas.upload import UploadErrorResponse

from pydantic import BaseModel, Field


class PdfConversionStatus(str, Enum):
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
    job_id: Optional[uuid.UUID] = None
    progress: int = Field(default=0, ge=0, le=100)
    external_job_id: Optional[str] = None
    output_path: Optional[str] = None
    output_paths: Optional[List[str]] = None
    error_summary: Optional[dict[str, Any]] = None


class PdfConvertIngestedUpload(BaseModel):
    filename: str
    process_id: uuid.UUID
    # Optional v2 import job created from this UploadJob.
    import_job_id: Optional[uuid.UUID] = None
    total_rows: int
    valid_rows: int
    invalid_rows: int
    sample_errors: List[UploadErrorResponse] = Field(default=[])
    csv_text: Optional[str] = None


class PdfConvertIngestResponse(BaseModel):
    uploads: List[PdfConvertIngestedUpload]


class PdfConvertOutputFile(BaseModel):
    filename: str
    csv_text: Optional[str] = None


class PdfConvertOutputsResponse(BaseModel):
    outputs: List[PdfConvertOutputFile]
