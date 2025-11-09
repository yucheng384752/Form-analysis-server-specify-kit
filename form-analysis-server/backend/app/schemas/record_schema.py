"""
記錄 Pydantic 模型

用於 API 請求和回應的資料驗證與序列化。
"""

import uuid
from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator
import re


class RecordBase(BaseModel):
    """記錄基礎模型"""
    
    lot_no: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="批號，格式：7數字_2數字（如：1234567_01）",
        examples=["1234567_01", "9876543_12"]
    )
    
    product_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="產品名稱，1-100字元",
        examples=["產品A", "高品質零件"]
    )
    
    quantity: int = Field(
        ...,
        ge=0,
        description="數量，非負整數",
        examples=[100, 500, 1000]
    )
    
    production_date: date = Field(
        ...,
        description="生產日期，格式：YYYY-MM-DD",
        examples=["2025-11-08", "2025-12-01"]
    )
    
    @field_validator('lot_no')
    @classmethod
    def validate_lot_no_format(cls, v: str) -> str:
        """驗證批號格式"""
        if not re.match(r'^\d{7}_\d{2}$', v):
            raise ValueError('批號格式不正確，應為 7數字_2數字 格式（如：1234567_01）')
        return v
    
    @field_validator('product_name')
    @classmethod
    def validate_product_name(cls, v: str) -> str:
        """驗證產品名稱"""
        v = v.strip()
        if not v:
            raise ValueError('產品名稱不能為空')
        return v


class RecordCreate(RecordBase):
    """建立記錄的請求模型"""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "lot_no": "2503033_03",
                "product_name": "高品質零件A",
                "quantity": 500,
                "production_date": "2025-11-08"
            }
        }
    )


class RecordRead(RecordBase):
    """記錄回應模型"""
    
    id: uuid.UUID = Field(
        ...,
        description="記錄ID"
    )
    
    created_at: datetime = Field(
        ...,
        description="記錄建立時間"
    )
    
    model_config = ConfigDict(
        from_attributes=True,  # 支援從 SQLAlchemy 模型轉換
        json_schema_extra={
            "example": {
                "id": "789e1234-e89b-12d3-a456-426614174002",
                "lot_no": "2503033_03",
                "product_name": "高品質零件A",
                "quantity": 500,
                "production_date": "2025-11-08",
                "created_at": "2025-11-08T10:32:00Z"
            }
        }
    )