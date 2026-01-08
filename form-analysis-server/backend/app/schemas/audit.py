from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class EditReasonResponse(BaseModel):
    id: UUID
    reason_code: str
    description: str
    display_order: int

    class Config:
        from_attributes = True

class RecordUpdateRequest(BaseModel):
    updates: Dict[str, Any] = Field(..., description="Fields to update")
    reason_id: Optional[UUID] = Field(None, description="Selected reason ID")
    reason_text: Optional[str] = Field(None, description="Custom reason text or snapshot of reason")

class RowEditResponse(BaseModel):
    id: UUID
    table_code: str
    record_id: UUID
    reason_text: Optional[str]
    before_json: Dict[str, Any]
    after_json: Dict[str, Any]
    created_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True
