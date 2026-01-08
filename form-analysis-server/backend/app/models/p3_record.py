from typing import Optional
from sqlalchemy import String, Integer, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base_record import BaseRecordMixin

class P3Record(BaseRecordMixin, Base):
    __tablename__ = "p3_records"
    
    production_date_yyyymmdd: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Production Date (YYYYMMDD)"
    )
    
    machine_no: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Machine No (e.g. P24)"
    )
    
    mold_no: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Mold No (e.g. 238-2)"
    )
    
    product_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Derived Product ID (YYYY-MM-DD_machine_mold_lot)"
    )

    __table_args__ = (
        UniqueConstraint('tenant_id', 'production_date_yyyymmdd', 'machine_no', 'mold_no', 'lot_no_norm', name='uq_p3_composite_key'),
        Index('ix_p3_tenant_lot_norm', 'tenant_id', 'lot_no_norm'),
        Index('ix_p3_tenant_prod_machine_mold', 'tenant_id', 'production_date_yyyymmdd', 'machine_no', 'mold_no'),
    )
