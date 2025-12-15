"""
記錄 Pydantic 模型

用於 API 請求和回應的資料驗證與序列化。
"""

import uuid
from datetime import datetime, date
from typing import Optional, Dict, Any
from enum import Enum

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


class DataType(str, Enum):
    """資料類型枚舉"""
    P1 = "P1"
    P2 = "P2"  
    P3 = "P3"


class RecordRead(BaseModel):
    """記錄回應模型 - 支援完整的資料顯示"""
    
    id: uuid.UUID = Field(..., description="記錄ID")
    lot_no: str = Field(..., description="批號")
    data_type: DataType = Field(..., description="資料類型")
    production_date: Optional[date] = Field(None, description="生產日期")
    
    # P1/P3 共用欄位
    product_name: Optional[str] = Field(None, description="產品名稱")
    quantity: Optional[int] = Field(None, description="數量")
    notes: Optional[str] = Field(None, description="備註")
    
    # P3 專用欄位
    p3_no: Optional[str] = Field(None, description="P3追蹤編號")
    
    # P2 專用欄位
    sheet_width: Optional[float] = Field(None, description="片材寬度(mm)")
    thickness1: Optional[float] = Field(None, description="厚度1(μm)")
    thickness2: Optional[float] = Field(None, description="厚度2(μm)")
    thickness3: Optional[float] = Field(None, description="厚度3(μm)")
    thickness4: Optional[float] = Field(None, description="厚度4(μm)")
    thickness5: Optional[float] = Field(None, description="厚度5(μm)")
    thickness6: Optional[float] = Field(None, description="厚度6(μm)")
    thickness7: Optional[float] = Field(None, description="厚度7(μm)")
    appearance: Optional[int] = Field(None, description="外觀")
    rough_edge: Optional[int] = Field(None, description="粗糙邊緣")
    slitting_result: Optional[int] = Field(None, description="切割結果")
    
    # 額外欄位 (來自CSV的其他欄位)
    additional_data: Optional[Dict[str, Any]] = Field(
        None, 
        description="額外資料，包含CSV檔案中的其他欄位（如溫度資料等）"
    )
    
    created_at: datetime = Field(..., description="記錄建立時間")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "789e1234-e89b-12d3-a456-426614174002",
                    "lot_no": "2503213_02",
                    "data_type": "P1",
                    "product_name": "來自P1_2503213_02.csv的產品",
                    "quantity": 100,
                    "production_date": "2025-11-10",
                    "notes": "從P1檔案匯入的資料",
                    "additional_data": {
                        "batch_size": 1000,
                        "quality_grade": "A",
                        "inspector": "QA001"
                    },
                    "created_at": "2025-11-10T15:07:44Z"
                },
                {
                    "id": "456e7890-e89b-12d3-a456-426614174003",
                    "lot_no": "2503213_02",
                    "data_type": "P2",
                    "sheet_width": 150.0,
                    "thickness1": 194.0,
                    "thickness2": 195.0,
                    "thickness3": 194.0,
                    "thickness4": 193.0,
                    "thickness5": 193.0,
                    "thickness6": 195.0,
                    "thickness7": 194.0,
                    "production_date": "2025-11-10",
                    "additional_data": {
                        "Actual_Temp_C1": 194,
                        "Actual_Temp_C2": 195,
                        "Actual_Temp_C3": 194,
                        "Actual_Temp_C4": 193,
                        "Actual_Temp_C5": 193,
                        "Actual_Temp_C6": 195,
                        "Actual_Temp_C7": 194,
                        "operator": "OP001",
                        "equipment_id": "EQ002"
                    },
                    "created_at": "2025-11-10T15:07:44Z"
                }
            ]
        }
    )