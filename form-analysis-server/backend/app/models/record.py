"""
記錄模型

代表經過驗證並成功匯入的資料記錄。
支援 P1/P2/P3 三種不同類型的數據結構。
"""

import uuid
from datetime import datetime, date
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import String, Integer, Date, DateTime, func, Index, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DataType(str, Enum):
    """數據類型枚舉"""
    P1 = "P1"  # 產品基本資料
    P2 = "P2"  # 尺寸檢測資料  
    P3 = "P3"  # 追蹤編號


class Record(Base):
    """
    資料記錄模型
    
    儲存經過驗證並成功匯入的業務資料，支援P1/P2/P3三種不同的數據類型：
    - P1: 產品基本資料 (product_name, quantity, production_date, notes)
    - P2: 尺寸檢測資料 (sheet_width, thickness1-7, appearance, rough_edge, slitting_result)  
    - P3: 追蹤編號 (p3_no, product_name, quantity, production_date, notes)
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
        comment="數據類型：P1(產品基本資料), P2(尺寸檢測資料), P3(追蹤編號)"
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
    
    # P3 專用欄位
    p3_no: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="P3追蹤編號 (P3使用)"
    )
    
    # P2 專用欄位
    sheet_width: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="片材寬度(mm) (P2使用)"
    )
    
    thickness1: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="厚度1(μm) (P2使用)"
    )
    
    thickness2: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="厚度2(μm) (P2使用)"
    )
    
    thickness3: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="厚度3(μm) (P2使用)"
    )
    
    thickness4: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="厚度4(μm) (P2使用)"
    )
    
    thickness5: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="厚度5(μm) (P2使用)"
    )
    
    thickness6: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="厚度6(μm) (P2使用)"
    )
    
    thickness7: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="厚度7(μm) (P2使用)"
    )
    
    appearance: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="外觀 (P2使用，0或1)"
    )
    
    rough_edge: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="粗糙邊緣 (P2使用，0或1)"
    )
    
    slitting_result: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="切割結果 (P2使用，0或1)"
    )
    
    # 額外數據存儲 (JSONB格式，用於存儲CSV中的所有其他欄位)
    additional_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="額外數據，JSONB格式，用於存儲CSV檔案中的所有其他欄位（如溫度數據、自定義欄位等）"
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
            f"data_type={self.data_type}, production_date={self.production_date})>"
        )
    
    @property
    def display_name(self) -> str:
        """返回用於顯示的名稱"""
        if self.data_type == DataType.P1:
            return self.product_name or "未知產品"
        elif self.data_type == DataType.P2:
            return f"檢測數據 ({self.lot_no})"
        elif self.data_type == DataType.P3:
            return f"P3-{self.p3_no}" if self.p3_no else f"P3追蹤 ({self.lot_no})"
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