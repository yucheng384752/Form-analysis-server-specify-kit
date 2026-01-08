import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class EditReason(Base):
    __tablename__ = "edit_reasons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)

class RowEdit(Base):
    __tablename__ = "row_edits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    
    table_code: Mapped[str] = mapped_column(String(20), nullable=False, comment="P1, P2, P3")
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    reason_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("edit_reasons.id"), nullable=True)
    reason_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Custom reason or snapshot")
    
    before_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    after_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    reason: Mapped["EditReason"] = relationship("EditReason")
