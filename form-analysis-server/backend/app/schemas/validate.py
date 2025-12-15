"""
驗證結果 Schema 模型

用於 API 回應的驗證結果和錯誤項目資料結構。
"""

from typing import List, Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ErrorItem(BaseModel):
    """
    單一錯誤項目
    
    描述檔案驗證過程中發現的具體錯誤資訊。
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "row_index": 5,
                "field": "lot_no",
                "error_code": "INVALID_FORMAT",
                "message": "批號格式錯誤，應為7位數字_2位數字格式，實際值：123456_01"
            }
        }
    )
    
    row_index: int = Field(
        ...,
        description="發生錯誤的行索引（從1開始，不包含標題行）",
        ge=1,
        examples=[5, 10, 15]
    )
    
    field: str = Field(
        ...,
        description="發生錯誤的欄位名稱",
        max_length=100,
        examples=["lot_no", "product_name", "quantity", "production_date"]
    )
    
    error_code: str = Field(
        ...,
        description="錯誤類型程式碼",
        max_length=50,
        examples=[
            "INVALID_FORMAT",    # 格式錯誤
            "REQUIRED_FIELD",    # 必填欄位為空
            "INVALID_VALUE",     # 值不符合規範
            "OUT_OF_RANGE"       # 超出範圍
        ]
    )
    
    message: str = Field(
        ...,
        description="詳細的錯誤描述訊息",
        max_length=500,
        examples=[
            "批號格式錯誤，應為7位數字_2位數字格式",
            "產品名稱不能為空",
            "數量必須為非負整數",
            "生產日期格式錯誤，應為YYYY-MM-DD格式"
        ]
    )


class ValidateResult(BaseModel):
    """
    驗證結果回應模型
    
    包含工作基本資訊、統計資料和錯誤項目列表（支援分頁）。
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "process_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "filename": "product_data.csv",
                "status": "VALIDATED",
                "created_at": "2024-01-01T10:30:00Z",
                "statistics": {
                    "total_rows": 100,
                    "valid_rows": 85,
                    "invalid_rows": 15
                },
                "errors": [
                    {
                        "row_index": 5,
                        "field": "lot_no",
                        "error_code": "INVALID_FORMAT",
                        "message": "批號格式錯誤，應為7位數字_2位數字格式，實際值：123456_01"
                    }
                ],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total_errors": 15,
                    "total_pages": 1,
                    "has_next": False,
                    "has_prev": False
                }
            }
        }
    )
    
    # 工作基本資訊
    job_id: UUID = Field(
        ...,
        description="上傳工作的唯一識別碼"
    )
    
    process_id: UUID = Field(
        ...,
        description="處理流程識別碼"
    )
    
    filename: str = Field(
        ...,
        description="原始檔案名稱",
        max_length=255
    )
    
    status: str = Field(
        ...,
        description="工作狀態",
        examples=["PENDING", "VALIDATED", "IMPORTED"]
    )
    
    created_at: datetime = Field(
        ...,
        description="工作建立時間"
    )
    
    # 統計資訊
    statistics: dict = Field(
        ...,
        description="驗證統計資訊",
        examples=[{
            "total_rows": 100,
            "valid_rows": 85,
            "invalid_rows": 15
        }]
    )
    
    # 錯誤列表
    errors: List[ErrorItem] = Field(
        default_factory=list,
        description="錯誤項目列表（當前頁面）"
    )
    
    # 分頁資訊
    pagination: dict = Field(
        ...,
        description="分頁資訊",
        examples=[{
            "page": 1,
            "page_size": 20,
            "total_errors": 15,
            "total_pages": 1,
            "has_next": False,
            "has_prev": False
        }]
    )


class PaginationParams(BaseModel):
    """
    分頁參數模型
    
    用於驗證查詢參數中的分頁設定。
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "page": 1,
                "page_size": 20
            }
        }
    )
    
    page: int = Field(
        default=1,
        description="頁碼（從1開始）",
        ge=1,
        examples=[1, 2, 5]
    )
    
    page_size: int = Field(
        default=20,
        description="每頁項目數量",
        ge=1,
        le=100,
        examples=[10, 20, 50]
    )


class ErrorNotFoundResponse(BaseModel):
    """
    找不到工作時的錯誤回應
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "找不到指定的上傳工作",
                "process_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "error_code": "JOB_NOT_FOUND"
            }
        }
    )
    
    detail: str = Field(
        ...,
        description="錯誤描述"
    )
    
    process_id: UUID = Field(
        ...,
        description="請求的 Process ID"
    )
    
    error_code: str = Field(
        default="JOB_NOT_FOUND",
        description="錯誤程式碼"
    )