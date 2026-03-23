import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImportStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )

    batch_id: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, comment="批次ID"
    )
    status: Mapped[ImportStatus] = mapped_column(
        SQLEnum(ImportStatus), default=ImportStatus.PENDING
    )

    total_files: Mapped[int] = mapped_column(Integer, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ImportFile(Base):
    __tablename__ = "import_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256"
    )
    table_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="P1/P2/P3"
    )

    status: Mapped[ImportStatus] = mapped_column(
        SQLEnum(ImportStatus), default=ImportStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StagingRow(Base):
    __tablename__ = "staging_rows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_files.id"), nullable=False
    )

    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_errors: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
