from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    id: UUID
    created_at: datetime

    tenant_id: Optional[UUID]
    actor_api_key_id: Optional[UUID]
    actor_label_snapshot: Optional[str]

    request_id: Optional[str]
    method: str
    path: str
    status_code: int

    client_host: Optional[str]
    user_agent: Optional[str]

    action: str
    metadata_json: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
