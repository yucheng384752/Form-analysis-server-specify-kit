"""P2 Items V2 Model - Stores expanded P2 row data (one record per winder)"""
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class P2ItemV2(Base):
    """P2 明細資料 - 每個 winder 一筆記錄"""
    __tablename__ = "p2_items_v2"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    p2_record_id = Column(UUID(as_uuid=True), ForeignKey("p2_records.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    winder_number = Column(Integer, nullable=False)
    
    # P2 Data Fields
    sheet_width = Column(Float)
    thickness1 = Column(Float)
    thickness2 = Column(Float)
    thickness3 = Column(Float)
    thickness4 = Column(Float)
    thickness5 = Column(Float)
    thickness6 = Column(Float)
    thickness7 = Column(Float)
    appearance = Column(Integer)
    rough_edge = Column(Integer)
    slitting_result = Column(Integer)
    
    # Original row data from CSV
    row_data = Column(JSONB)

    @staticmethod
    def _utcnow():
        return datetime.now(timezone.utc)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    
    # Relationships
    p2_record = relationship("P2Record", back_populates="items_v2")
    tenant = relationship("Tenant")
    
    __table_args__ = (
        Index("ix_p2_items_v2_p2_record_id", "p2_record_id"),
        Index("ix_p2_items_v2_tenant_id", "tenant_id"),
        Index("ix_p2_items_v2_winder_number", "winder_number"),
        Index("ix_p2_items_v2_row_data_gin", "row_data", postgresql_using="gin"),
        UniqueConstraint("p2_record_id", "winder_number", name="uq_p2_items_v2_record_winder"),
    )
    
    def __repr__(self):
        return f"<P2ItemV2(id={self.id}, p2_record_id={self.p2_record_id}, winder={self.winder_number})>"
