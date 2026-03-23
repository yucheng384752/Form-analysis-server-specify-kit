from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EditReasonResponse(BaseModel):
    id: UUID
    reason_code: str
    description: str
    display_order: int

    model_config = ConfigDict(from_attributes=True)


class RecordUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(..., description="Fields to update")
    reason_id: UUID | None = Field(None, description="Selected reason ID")
    reason_text: str | None = Field(
        None, description="Custom reason text or snapshot of reason"
    )


class EditReasonCreateRequest(BaseModel):
    reason_code: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=255)
    display_order: int = Field(0, ge=0)
    is_active: bool = Field(True)


class EditReasonUpdateRequest(BaseModel):
    description: str | None = Field(None, min_length=1, max_length=255)
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class EditRecordRequest(BaseModel):
    """Unified request body for inline edit.

    Supports both:
    - New (recommended) flat payload: {tenant_id?, updates, reason_id?, reason_text?}
    - Legacy payload: {tenant_id, request: {updates, reason_id?, reason_text?}}
    """

    tenant_id: UUID | None = Field(
        None,
        description="Optional tenant id; prefer X-Tenant-Id header or API key bound tenant",
    )

    updates: dict[str, Any] = Field(..., description="Fields to update")
    reason_id: UUID | None = Field(None, description="Selected reason ID")
    reason_text: str | None = Field(
        None, description="Custom reason text or snapshot of reason"
    )

    # Backward-compat only
    request: RecordUpdateRequest | None = Field(
        None,
        description="Legacy nested request payload (deprecated)",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Legacy: { tenant_id: ..., request: { updates, reason_id, reason_text } }
        if "request" in data and "updates" not in data:
            nested = data.get("request")
            if isinstance(nested, dict):
                merged = dict(data)
                for key in ("updates", "reason_id", "reason_text"):
                    if key in nested and merged.get(key) is None:
                        merged[key] = nested.get(key)
                return merged

        return data


class RowEditResponse(BaseModel):
    id: UUID
    table_code: str
    record_id: UUID
    reason_text: str | None
    before_json: dict[str, Any]
    after_json: dict[str, Any]
    created_at: datetime
    created_by: str | None

    model_config = ConfigDict(from_attributes=True)
