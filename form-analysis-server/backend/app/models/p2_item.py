"""
P2 明細項目模型

P2 每一列的詳細記錄（對應一個卷收機 winder），用於支援逐列查詢與追溯。
與 Record 表建立父子關係（一對多）。
"""

import uuid
from typing import Optional

from sqlalchemy import String, Integer, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class P2Item(Base):
    """
    P2 明細項目模型
    
    儲存 P2 檔案中每一列的詳細資料（每個 winder 的測量結果），支援：
    - 逐列查詢與篩選
    - 透過 winder_number 與 P3 進行關聯追溯
    
    關聯關係：
    - 多個 P2Item 屬於一個 Record（P2 父表）
    - 透過 record_id 外鍵關聯
    """
    
    __tablename__ = "p2_items"
    
    # 主鍵
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="P2 明細項目唯一識別碼"
    )
    
    # 外鍵：關聯到父表 records
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="關聯的 Record ID（P2 父表）"
    )
    
    # 卷收機編號 (1-20)
    winder_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="卷收機編號 (1-20)"
    )
    
    # 測量數據
    sheet_width: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Sheet Width (mm)"
    )
    
    thickness1: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Thickness 1 (μm)")
    thickness2: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Thickness 2 (μm)")
    thickness3: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Thickness 3 (μm)")
    thickness4: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Thickness 4 (μm)")
    thickness5: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Thickness 5 (μm)")
    thickness6: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Thickness 6 (μm)")
    thickness7: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Thickness 7 (μm)")
    
    # 品質判定
    appearance: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="外觀判定 (1=OK, 0=NG)"
    )
    
    rough_edge: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="毛邊判定 (1=OK, 0=NG)"
    )
    
    slitting_result: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="分條結果 (1=OK, 0=NG)"
    )
    
    # 原始資料
    row_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="原始列資料 (JSON)"
    )
    
    # 關聯
    record = relationship("Record", back_populates="p2_items")

    # 索引與約束
    __table_args__ = (
        # 複合索引：加速 record_id + winder_number 查詢
        Index("ix_p2_items_record_winder", "record_id", "winder_number"),
        # 唯一約束：同一個 record 下 winder_number 不可重複
        UniqueConstraint("record_id", "winder_number", name="uq_p2_items_record_winder"),
    )

    def __repr__(self):
        return f"<P2Item(id={self.id}, winder={self.winder_number})>"
