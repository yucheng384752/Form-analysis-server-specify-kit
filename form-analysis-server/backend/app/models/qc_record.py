"""QC Record Model - 打孔帶生產日報表"""

import uuid
from datetime import UTC, datetime, date
from typing import Any

from sqlalchemy import Column, Date, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from app.core.database import Base


class QcRecord(Base):
    """QC 日報表 - 每機台每日一筆"""

    __tablename__ = "qc_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    production_date = Column(Date, nullable=False)
    machine_no = Column(String(20), nullable=False)
    source_file = Column(String(200), nullable=True)  # 原始 PDF 檔名

    # QC 檢驗值
    qc_A_H = Column(Float, nullable=True)
    qc_A_L = Column(Float, nullable=True)
    qc_B_H = Column(Float, nullable=True)
    qc_B_L = Column(Float, nullable=True)
    qc_E_prime_H = Column(Float, nullable=True)
    qc_E_prime_L = Column(Float, nullable=True)
    qc_10P0_H = Column(Float, nullable=True)
    qc_10P0_L = Column(Float, nullable=True)
    qc_bending = Column(Integer, nullable=True)
    qc_result = Column(String(50), nullable=True)   # "No NG" / "1NG" ...

    # 生產摘要
    ng_count = Column(Integer, nullable=False, default=0)
    bad_reason = Column(String(200), nullable=True)

    # 各卷明細（JSONB）
    rolls_data = Column(JSONB, nullable=True)
    # [{"roll_no": 1, "judgment": "OK", "thickness_H": 322, "thickness_L": 309}, ...]

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(UTC)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "production_date", "machine_no",
            name="uq_qc_record_date_machine",
        ),
        Index("ix_qc_tenant_date", "tenant_id", "production_date"),
        Index("ix_qc_tenant_machine", "tenant_id", "machine_no"),
        Index("ix_qc_result", "qc_result"),
    )

    def __repr__(self) -> str:
        return f"<QcRecord(machine={self.machine_no}, date={self.production_date})>"
