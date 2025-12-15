"""
上傳錯誤 Pydantic 模型

用於 API 請求和回應的資料驗證與序列化。
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class UploadErrorBase(BaseModel):
    """上傳錯誤基礎模型"""
    
    row_index: int = Field(
        ...,
        ge=0,
        description="發生錯誤的行索引（從0開始）"
    )
    
    field: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="發生錯誤的欄位名稱",
        examples=["lot_no", "product_name", "quantity"]
    )
    
    error_code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="錯誤程式碼",
        examples=["INVALID_FORMAT", "REQUIRED_FIELD", "INVALID_DATE"]
    )
    
    message: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="錯誤訊息描述"
    )


class UploadErrorCreate(UploadErrorBase):
    """建立上傳錯誤的請求模型"""
    
    job_id: uuid.UUID = Field(
        ...,
        description="關聯的上傳工作ID"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "row_index": 15,
                "field": "lot_no",
                "error_code": "INVALID_FORMAT",
                "message": "批號格式不正確，應為 7數字_2數字 格式"
            }
        }
    )


class UploadErrorRead(UploadErrorBase):
    """上傳錯誤回應模型"""
    
    id: uuid.UUID = Field(
        ...,
        description="錯誤記錄ID"
    )
    
    job_id: uuid.UUID = Field(
        ...,
        description="關聯的上傳工作ID"
    )
    
    created_at: datetime = Field(
        ...,
        description="錯誤記錄建立時間"
    )
    
    model_config = ConfigDict(
        from_attributes=True,  # 支援從 SQLAlchemy 模型轉換
        json_schema_extra={
            "example": {
                "id": "456e7890-e89b-12d3-a456-426614174001",
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "row_index": 15,
                "field": "lot_no",
                "error_code": "INVALID_FORMAT",
                "message": "批號格式不正確，應為 7數字_2數字 格式",
                "created_at": "2025-11-08T10:31:00Z"
            }
        }
    )