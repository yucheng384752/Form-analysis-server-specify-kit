import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EditReason(Base):
    __tablename__ = "edit_reasons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RowEdit(Base):
    __tablename__ = "row_edits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )

    table_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="p1_records, p2_records..."
    )
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    before_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    after_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    reason_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edit_reasons.id"), nullable=True
    )
    reason_text: Mapped[str | None] = mapped_column(
        String(255), comment="若選 Other 則填此"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(
        String(100), comment="User ID or Name"
    )
