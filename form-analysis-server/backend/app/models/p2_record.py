from sqlalchemy import Integer, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base_record import BaseRecordMixin

class P2Record(BaseRecordMixin, Base):
    __tablename__ = "p2_records"
    
    winder_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Winder Number (1-20)"
    )

    __table_args__ = (
        UniqueConstraint('tenant_id', 'lot_no_norm', 'winder_number', name='uq_p2_tenant_lot_winder'),
        Index('ix_p2_tenant_lot_norm', 'tenant_id', 'lot_no_norm'),
    )
