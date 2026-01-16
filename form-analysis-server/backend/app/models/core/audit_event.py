import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Context
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )
    actor_api_key_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tenant_api_keys.id"), nullable=True, index=True
    )
    actor_label_snapshot: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Request
    request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)

    client_host: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Classification
    action: Mapped[str] = mapped_column(String(50), nullable=False, default="http.request")

    # Extra details (keep small; do not store secrets)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default='{}')
