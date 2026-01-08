from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.import_job import ImportJobStatus

class ImportFileBase(BaseModel):
    filename: str
    file_size: int

class ImportFileRead(ImportFileBase):
    id: UUID
    file_hash: str
    row_count: int
    created_at: datetime

    class Config:
        from_attributes = True

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
    error_summary: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    files: List[ImportFileRead] = []

    class Config:
        from_attributes = True

class ImportJobSummary(BaseModel):
    id: UUID
    batch_id: str
    status: ImportJobStatus
    created_at: datetime
    total_files: int
    
    class Config:
        from_attributes = True

class ImportJobErrorRow(BaseModel):
    row_index: int
    file_id: UUID
    errors: List[Dict[str, Any]] = Field(validation_alias="errors_json")
    data: Dict[str, Any] = Field(validation_alias="parsed_json")

    class Config:
        from_attributes = True
        populate_by_name = True
