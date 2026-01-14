"""
檔案上傳相關的資料模型

定義檔案上傳和驗證回應的 Pydantic 模型。
"""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class UploadErrorResponse(BaseModel):
    """上傳錯誤回應模型"""
    
    row_index: int = Field(..., description="發生錯誤的行索引（從0開始）")
    field: str = Field(..., description="發生錯誤的欄位名稱")
    error_code: str = Field(..., description="錯誤程式碼")
    message: str = Field(..., description="錯誤訊息")


class FileUploadResponse(BaseModel):
    """檔案上傳回應模型"""
    
    process_id: uuid.UUID = Field(..., description="處理流程識別碼")
    total_rows: int = Field(..., description="總行數")
    valid_rows: int = Field(..., description="有效行數")
    invalid_rows: int = Field(..., description="無效行數")
    sample_errors: List[UploadErrorResponse] = Field(
        default=[], 
        description="錯誤樣本（前10筆）"
    )


class FileUploadRequest(BaseModel):
    """檔案上傳請求模型（用於文件）"""
    
    file: bytes = Field(..., description="上傳的檔案內容（form-data）")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "description": "使用 multipart/form-data 上傳 CSV 或 Excel 檔案",
                "content_type": "multipart/form-data",
                "fields": {
                    "file": "檔案內容（CSV 或 Excel 格式）"
                },
                "supported_formats": ["CSV (.csv)", "Excel (.xlsx, .xls)"],
                "required_columns": ["lot_no", "product_name", "quantity", "production_date"]
            }
        }
    )


class ValidationSummary(BaseModel):
    """驗證摘要模型"""
    
    filename: str = Field(..., description="檔案名稱")
    file_size: int = Field(..., description="檔案大小（位元組）")
    total_rows: int = Field(..., description="總行數")
    valid_rows: int = Field(..., description="有效行數") 
    invalid_rows: int = Field(..., description="無效行數")
    validation_time: float = Field(..., description="驗證耗時（秒）")
    created_at: datetime = Field(..., description="建立時間")


class UpdateUploadContentRequest(BaseModel):
    """更新上傳工作內容請求模型（前端表格修正用）"""

    csv_text: str = Field(..., description="修改後的 CSV 純文字內容（含表頭）")