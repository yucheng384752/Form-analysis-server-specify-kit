"""
資料匯入 Schema 模型

用於資料匯入 API 的請求和回應資料結構。
"""

from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ImportRequest(BaseModel):
    """
    匯入資料請求模型
    
    包含要匯入資料的處理流程識別碼。
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "process_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
            }
        }
    )
    
    process_id: UUID = Field(
        ...,
        description="處理流程識別碼，對應已驗證的上傳工作"
    )


class ImportResponse(BaseModel):
    """
    匯入資料回應模型
    
    包含匯入操作的結果統計資訊。
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "imported_rows": 85,
                "skipped_rows": 15,
                "elapsed_ms": 1250,
                "message": "資料匯入完成",
                "process_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
            }
        }
    )
    
    imported_rows: int = Field(
        ...,
        description="成功匯入的資料行數",
        ge=0
    )
    
    skipped_rows: int = Field(
        ...,
        description="跳過的無效資料行數",
        ge=0
    )
    
    elapsed_ms: int = Field(
        ...,
        description="匯入操作耗時（毫秒）",
        ge=0
    )
    
    message: str = Field(
        default="資料匯入完成",
        description="操作結果訊息"
    )
    
    process_id: UUID = Field(
        ...,
        description="處理流程識別碼"
    )


class ImportErrorResponse(BaseModel):
    """
    匯入錯誤回應模型
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "找不到指定的上傳工作或工作尚未驗證",
                "process_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "error_code": "JOB_NOT_READY"
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
        ...,
        description="錯誤代碼",
        examples=["JOB_NOT_FOUND", "JOB_NOT_READY", "JOB_ALREADY_IMPORTED"]
    )