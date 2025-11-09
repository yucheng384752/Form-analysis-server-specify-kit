"""
記錄模型

代表經過驗證並成功匯入的資料記錄。
"""

import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Integer, Date, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Record(Base):
    """
    資料記錄模型
    
    儲存經過驗證並成功匯入的業務資料，包含批號、產品資訊等。
    """
    __tablename__ = "records"

    # 主鍵 - 使用 UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="記錄ID"
    )
    
    # 業務資料欄位
    lot_no: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="批號，格式：7數字_2數字（如：1234567_01）"
    )
    
    product_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="產品名稱，1-100字元"
    )
    
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="數量，非負整數"
    )
    
    production_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="生產日期，格式：YYYY-MM-DD"
    )
    
    # 時間戳記
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="記錄建立時間"
    )
    
    def __repr__(self) -> str:
        return (
            f"<Record(id={self.id}, lot_no='{self.lot_no}', "
            f"product_name='{self.product_name}', quantity={self.quantity}, "
            f"production_date={self.production_date})>"
        )


# 為 lot_no 建立索引，用於常見的查詢操作
Index(
    "ix_records_lot_no",
    Record.lot_no,
    postgresql_using="btree"
)