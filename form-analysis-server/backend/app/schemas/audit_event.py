from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    id: UUID
    created_at: datetime

    tenant_id: UUID | None
    actor_api_key_id: UUID | None
    actor_label_snapshot: str | None

    request_id: str | None
    method: str
    path: str
    status_code: int

    client_host: str | None
    user_agent: str | None

    action: str
    metadata_json: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
