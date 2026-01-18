import uuid
from enum import Enum
from typing import Any, Optional

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
    error_summary: Optional[dict[str, Any]] = None
