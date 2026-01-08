"""
P3 明細項目模型

P3 每一列的詳細記錄，用於支援逐列查詢與追溯。
與 Record 表建立父子關係（一對多）。
"""

import uuid
from datetime import date, datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, Index, UniqueConstraint, func, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class P3Item(Base):
    """
    P3 明細項目模型
    
    儲存 P3 檔案中每一列的詳細資料，支援：
    - 逐列查詢與篩選
    - 產品編號追溯（P3 → P2 → P1）
    - 精準的品質與規格檢索
    
    關聯關係：
    - 多個 P3Item 屬於一個 Record（P3 父表）
    - 透過 record_id 外鍵關聯
    """
    
    __tablename__ = "p3_items"
    
    # 主鍵
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="P3 明細項目唯一識別碼"
    )
    
    # 外鍵：關聯到父表 records
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="關聯的 Record ID（P3 父表）"
    )
    
    # 列序號（在檔案中的順序，從 1 開始）
    row_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="該列在 CSV 檔案中的順序（1-based）"
    )
    
    # 產品編號（業務唯一鍵，用於追溯）
    product_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="產品編號（格式: YYYY-MM-DD_machine_mold_lot）"
    )
    
    # 批號（繼承自父表，方便直接查詢）
    lot_no: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="批號（標準格式: 7位數字_2位數字）"
    )
    
    # 生產日期
    production_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="生產日期（西元年 YYYY-MM-DD）"
    )
    
    # 機台編號
    machine_no: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="機台編號（如: P24, P21）"
    )
    
    # 模具編號
    mold_no: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="模具編號（如: 238-2, 123-1）"
    )
    
    # 生產序號（lot）
    production_lot: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="生產序號/批次號"
    )
    
    # 來源收卷機編號（用於追溯 P2）
    source_winder: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="來源收卷機編號（對應 P2 的 winder_number）"
    )
    
    # 規格
    specification: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="產品規格（如: PE 32）"
    )
    
    # 下膠編號
    bottom_tape_lot: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="下膠編號/Bottom Tape LOT"
    )
    
    # 該列的完整原始資料 (JSONB)
    row_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="該列的完整原始資料（JSON 格式）"
    )
    
    # 時間戳欄位
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="記錄建立時間"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="記錄更新時間"
    )
    
    # 關聯到父表
    record: Mapped["Record"] = relationship(
        "Record",
        back_populates="p3_items"
    )
    
    def __repr__(self) -> str:
        return (
            f"<P3Item(id={self.id}, product_id={self.product_id}, "
            f"row_no={self.row_no}, lot_no={self.lot_no})>"
        )


# 為常用查詢建立複合索引
Index(
    "ix_p3_items_record_id_row_no",
    P3Item.record_id,
    P3Item.row_no,
    postgresql_using="btree"
)

Index(
    "ix_p3_items_lot_no_row_no",
    P3Item.lot_no,
    P3Item.row_no,
    postgresql_using="btree"
)

# 確保 product_id 的唯一性
UniqueConstraint(
    P3Item.product_id,
    name='uq_p3_items_product_id'
)
