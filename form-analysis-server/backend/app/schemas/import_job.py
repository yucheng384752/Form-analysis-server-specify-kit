from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.import_job import ImportJobStatus


class ImportFileBase(BaseModel):
    filename: str
    file_size: int


class ImportFileRead(ImportFileBase):
    id: UUID
    file_hash: str
    row_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportJobCreate(BaseModel):
    table_code: str = Field(..., description="Target table code (e.g., 'P1', 'P2')")


class ImportJobRead(BaseModel):
    id: UUID
    batch_id: str
    tenant_id: UUID
    table_id: UUID
    status: ImportJobStatus
    progress: int
    total_files: int
    total_rows: int
    error_count: int
    error_summary: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    last_status_changed_at: datetime | None = None
    last_status_actor_kind: str | None = None
    last_status_actor_api_key_id: UUID | None = None
    last_status_actor_label_snapshot: str | None = None
    files: list[ImportFileRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ImportJobSummary(BaseModel):
    id: UUID
    batch_id: str
    status: ImportJobStatus
    created_at: datetime
    total_files: int

    model_config = ConfigDict(from_attributes=True)


class ImportJobErrorRow(BaseModel):
    row_index: int
    file_id: UUID
    errors: list[dict[str, Any]] = Field(validation_alias="errors_json")
    data: dict[str, Any] = Field(validation_alias="parsed_json")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
