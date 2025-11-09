"""
上傳工作 Pydantic 模型

用於 API 請求和回應的資料驗證與序列化。
"""

import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from app.models.upload_job import JobStatus


class UploadJobBase(BaseModel):
    """上傳工作基礎模型"""
    
    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="檔案名稱",
        examples=["data_2025.csv"]
    )
    
    status: JobStatus = Field(
        default=JobStatus.PENDING,
        description="處理狀態"
    )


class UploadJobCreate(UploadJobBase):
    """建立上傳工作的請求模型"""
    
    process_id: Optional[uuid.UUID] = Field(
        default=None,
        description="處理流程ID，如不提供則自動產生"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "filename": "product_data_2025.csv",
                "status": "PENDING",
                "process_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
    )


class UploadJobUpdate(BaseModel):
    """更新上傳工作的請求模型"""
    
    status: Optional[JobStatus] = Field(
        default=None,
        description="處理狀態"
    )
    
    total_rows: Optional[int] = Field(
        default=None,
        ge=0,
        description="總行數"
    )
    
    valid_rows: Optional[int] = Field(
        default=None,
        ge=0,
        description="有效行數"
    )
    
    invalid_rows: Optional[int] = Field(
        default=None,
        ge=0,
        description="無效行數"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "VALIDATED",
                "total_rows": 1000,
                "valid_rows": 980,
                "invalid_rows": 20
            }
        }
    )


class UploadJobRead(UploadJobBase):
    """上傳工作回應模型"""
    
    id: uuid.UUID = Field(
        ...,
        description="工作ID"
    )
    
    created_at: datetime = Field(
        ...,
        description="建立時間"
    )
    
    total_rows: Optional[int] = Field(
        default=None,
        description="總行數"
    )
    
    valid_rows: Optional[int] = Field(
        default=None,
        description="有效行數"
    )
    
    invalid_rows: Optional[int] = Field(
        default=None,
        description="無效行數"
    )
    
    process_id: uuid.UUID = Field(
        ...,
        description="處理流程識別碼"
    )
    
    # 可選包含錯誤列表
    errors: Optional[List["UploadErrorRead"]] = Field(
        default=None,
        description="相關錯誤列表"
    )
    
    model_config = ConfigDict(
        from_attributes=True,  # 支援從 SQLAlchemy 模型轉換
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "filename": "product_data_2025.csv",
                "status": "VALIDATED",
                "created_at": "2025-11-08T10:30:00Z",
                "total_rows": 1000,
                "valid_rows": 980,
                "invalid_rows": 20,
                "process_id": "550e8400-e29b-41d4-a716-446655440000",
                "errors": []
            }
        }
    )


# 避免循環匯入，在模組末尾處理 forward references
from app.schemas.upload_error_schema import UploadErrorRead
UploadJobRead.model_rebuild()