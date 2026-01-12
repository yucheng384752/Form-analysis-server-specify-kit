"""
[DEPRECATED] This model is being replaced by P1Record, P2Record, and P3Record.
Please do not use this model for new features.

記錄模型

代表經過驗證並成功匯入的資料記錄。
支援 P1/P2/P3 三種不同類型的資料結構。
"""

import uuid
from datetime import datetime, date
from typing import Optional, Dict, Any, TYPE_CHECKING
from enum import Enum

from sqlalchemy import String, Integer, Date, DateTime, func, Index, Text, Enum as SQLEnum, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.p3_item import P3Item
    from app.models.p2_item import P2Item


class DataType(str, Enum):
    """資料類型枚舉"""
    P1 = "P1"  # 產品基本資料
    P2 = "P2"  # 尺寸檢測資料  
    P3 = "P3"  # 追蹤編號


class Record(Base):
    """
    資料記錄模型
    
    儲存經過驗證並成功匯入的業務資料，支援 P1/P2/P3 三種不同的資料類型：
    
    - P1: 產品基本資料
      * 批號 (lot_no)
      * 材料代碼 (material_code)
      * 生產日期 (production_date)
      * 其他製程參數存於 additional_data
      
    - P2: 尺寸檢測資料
      * 批號 (lot_no)
      * 材料代碼 (material_code)
      * 分條機編號 (slitting_machine_number)
      * 分條編號 (winder_number)：1-20
      * 厚度檢測資料 (thickness1-7, sheet_width等)
      * 品質檢測 (appearance, rough_edge, slitting_result)
      
    - P3: 追蹤編號（成品加工資料）
      * 批號 (lot_no)：標準化格式
      * Product ID (product_id)：唯一識別碼 YYYY-MM-DD_machine_mold_lot
      * 生產機台 (machine_no)：P24, P21 等
      * 模具編號 (mold_no)：238-2 等
      * 生產序號 (production_lot)：301, 302 等
      * 來源分條 (source_winder)：用於追溯到對應的 P2 記錄
      * 其他品質資料存於 additional_data
    """
    __tablename__ = "records"

    # 主鍵 - 使用 UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="記錄ID"
    )
    
    # 基本欄位
    lot_no: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="批號，格式：7數字_2數字（如：1234567_01）"
    )
    
    data_type: Mapped[DataType] = mapped_column(
        SQLEnum(DataType, name="data_type_enum"),
        nullable=False,
        comment="資料類型：P1(產品基本資料), P2(尺寸檢測資料), P3(追蹤編號)"
    )
    
    # 生產日期 (所有類型共有)
    production_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="生產日期，格式：YYYY-MM-DD"
    )
    
    # P1 專用欄位
    product_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="產品名稱 (P1/P3使用)"
    )
    
    quantity: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="數量 (P1/P3使用)"
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="備註 (P1/P3使用)"
    )
    
    # ==================== 材料與機台欄位（新增） ====================
    
    # 材料代碼 (P1, P2 使用)
    material_code: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        index=True,
        comment="材料代碼 (P1/P2使用)：H2, H5, H8 等"
    )

    # Added for migration compatibility - columns exist in DB
    winder_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slitting_machine_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    sheet_width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thickness1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thickness2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thickness3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thickness4: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thickness5: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thickness6: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thickness7: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    appearance: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rough_edge: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slitting_result: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    machine_no: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mold_no: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    production_lot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_winder: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    p3_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 額外資料存儲 (JSONB格式，用於存儲CSV中的所有其他欄位)
    additional_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="額外資料，JSONB格式，用於存儲CSV檔案中的所有其他欄位（如溫度資料、自定義欄位等）"
    )
    
    # 時間戳記
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="記錄建立時間"
    )
    
    # P3 明細項目關聯（一對多）
    p3_items: Mapped[list["P3Item"]] = relationship(
        "P3Item",
        back_populates="record",
        cascade="all, delete-orphan"
    )
    
    # P2 明細項目關聯（一對多）
    p2_items: Mapped[list["P2Item"]] = relationship(
        "P2Item",
        back_populates="record",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return (
            f"<Record(id={self.id}, lot_no='{self.lot_no}', "
            f"data_type={self.data_type}, production_date={self.production_date})>"
        )
    
    @property
    def display_name(self) -> str:
        """返回用於顯示的名稱"""
        if self.data_type == DataType.P1:
            return self.product_name or "未知產品"
        elif self.data_type == DataType.P2:
            return f"檢測資料 ({self.lot_no})"
        elif self.data_type == DataType.P3:
            return f"P3追蹤 ({self.lot_no})"
        return f"{self.data_type} ({self.lot_no})"


# 為常用查詢建立複合索引
Index(
    "ix_records_lot_no_data_type",
    Record.lot_no,
    Record.data_type,
    postgresql_using="btree"
)

# 為 lot_no 建立單獨索引
Index(
    "ix_records_lot_no",
    Record.lot_no,
    postgresql_using="btree"
)

# 為 data_type 建立單獨索引  
Index(
    "ix_records_data_type",
    Record.data_type,
    postgresql_using="btree"
)

# 添加唯一約束防止重複資料
# 同一個 lot_no 和 data_type 組合不允許重複
from sqlalchemy import UniqueConstraint
UniqueConstraint(
    Record.lot_no,
    Record.data_type,
    name='uq_records_lot_no_data_type'
)