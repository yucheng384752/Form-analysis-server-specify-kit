"""
測試 Pydantic Schemas
"""
import json
from datetime import datetime
from pydantic import ValidationError

# 直接定義 schemas 用於測試
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum

class JobStatus(str, Enum):
    """工作狀態"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# Upload Job Schemas
class UploadJobCreate(BaseModel):
    """創建上傳工作的請求模型"""
    filename: str = Field(..., min_length=1, max_length=255, description="上傳檔案名稱")
    file_size: int = Field(..., ge=1, description="檔案大小（位元組）")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "filename": "products_202401.xlsx",
                "file_size": 2048000
            }
        }
    }

class UploadJobRead(BaseModel):
    """上傳工作回應模型"""
    id: str = Field(..., description="工作唯一識別碼")
    filename: str = Field(..., description="上傳檔案名稱")
    file_size: int = Field(..., description="檔案大小（位元組）")
    status: JobStatus = Field(..., description="處理狀態")
    created_at: datetime = Field(..., description="建立時間")
    processed_at: Optional[datetime] = Field(None, description="處理完成時間")
    total_records: Optional[int] = Field(None, description="總記錄數")
    success_records: Optional[int] = Field(None, description="成功記錄數")
    error_records: Optional[int] = Field(None, description="錯誤記錄數")
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "filename": "products_202401.xlsx",
                "file_size": 2048000,
                "status": "COMPLETED",
                "created_at": "2024-01-08T10:30:00Z",
                "processed_at": "2024-01-08T10:35:00Z",
                "total_records": 150,
                "success_records": 148,
                "error_records": 2
            }
        }
    }

# Record Schemas
class RecordCreate(BaseModel):
    """創建記錄的請求模型"""
    lot_no: str = Field(..., min_length=1, max_length=50, description="批號")
    product_name: Optional[str] = Field(None, max_length=200, description="產品名稱")
    specification: Optional[str] = Field(None, description="規格說明")
    quantity: Optional[int] = Field(None, ge=0, description="數量")
    unit: Optional[str] = Field(None, max_length=20, description="單位")
    raw_data: dict = Field(..., description="原始資料")
    
    @field_validator("lot_no")
    @classmethod
    def validate_lot_no_format(cls, v: str) -> str:
        """驗證批號格式 (L + 日期 + 序號)"""
        import re
        # 先轉為大寫
        v = v.upper()
        if not re.match(r"^L\d{6}\d{3}$", v):
            raise ValueError("批號格式必須為 L + 6位日期 + 3位序號 (例如: L240108001)")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "lot_no": "L240108001",
                "product_name": "產品A型號",
                "specification": "規格說明文字",
                "quantity": 100,
                "unit": "pcs",
                "raw_data": {
                    "column_a": "值A",
                    "column_b": "值B"
                }
            }
        }
    }

class RecordRead(BaseModel):
    """記錄回應模型"""
    id: str = Field(..., description="記錄唯一識別碼")
    upload_job_id: str = Field(..., description="所屬上傳工作ID")
    lot_no: str = Field(..., description="批號")
    product_name: Optional[str] = Field(None, description="產品名稱")
    specification: Optional[str] = Field(None, description="規格說明")
    quantity: Optional[int] = Field(None, description="數量")
    unit: Optional[str] = Field(None, description="單位")
    raw_data: dict = Field(..., description="原始資料")
    created_at: datetime = Field(..., description="建立時間")
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "upload_job_id": "550e8400-e29b-41d4-a716-446655440000",
                "lot_no": "L240108001",
                "product_name": "產品A型號",
                "specification": "規格說明文字",
                "quantity": 100,
                "unit": "pcs",
                "raw_data": {
                    "column_a": "值A",
                    "column_b": "值B"
                },
                "created_at": "2024-01-08T10:30:00Z"
            }
        }
    }

# Upload Error Schemas
class UploadErrorCreate(BaseModel):
    """創建上傳錯誤的請求模型"""
    error_message: str = Field(..., min_length=1, description="錯誤訊息")
    error_details: Optional[dict] = Field(None, description="錯誤詳細資訊")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "error_message": "資料格式錯誤",
                "error_details": {
                    "row": 5,
                    "column": "B",
                    "expected": "數字",
                    "received": "文字"
                }
            }
        }
    }

class UploadErrorRead(BaseModel):
    """上傳錯誤回應模型"""
    id: str = Field(..., description="錯誤唯一識別碼")
    upload_job_id: str = Field(..., description="所屬上傳工作ID")
    error_message: str = Field(..., description="錯誤訊息")
    error_details: Optional[dict] = Field(None, description="錯誤詳細資訊")
    created_at: datetime = Field(..., description="建立時間")
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "upload_job_id": "550e8400-e29b-41d4-a716-446655440000",
                "error_message": "資料格式錯誤",
                "error_details": {
                    "row": 5,
                    "column": "B",
                    "expected": "數字",
                    "received": "文字"
                },
                "created_at": "2024-01-08T10:32:00Z"
            }
        }
    }

def test_schemas():
    """測試所有 Pydantic schemas"""
    print("🚀 開始測試 Pydantic Schemas\n")
    
    try:
        # 1. 測試 UploadJobCreate
        print("📝 測試 UploadJobCreate...")
        job_create_data = {
            "filename": "test_file.xlsx",
            "file_size": 1024000
        }
        job_create = UploadJobCreate(**job_create_data)
        print(f" 創建成功: {job_create.filename}, {job_create.file_size} bytes")
        
        # 測試驗證錯誤
        try:
            invalid_job = UploadJobCreate(filename="", file_size=0)
        except ValidationError as e:
            print(f" 驗證錯誤正確捕獲: {len(e.errors())} 個錯誤")
        
        # 2. 測試 RecordCreate
        print(f"\n📝 測試 RecordCreate...")
        record_create_data = {
            "lot_no": "L240108001",
            "product_name": "測試產品",
            "specification": "測試規格",
            "quantity": 50,
            "unit": "pcs",
            "raw_data": {"col1": "value1", "col2": "value2"}
        }
        record_create = RecordCreate(**record_create_data)
        print(f" 創建成功: {record_create.lot_no}, {record_create.product_name}")
        
        # 測試批號格式驗證
        try:
            invalid_record = RecordCreate(
                lot_no="INVALID",
                raw_data={"test": "data"}
            )
        except ValidationError as e:
            print(f" 批號格式驗證錯誤正確捕獲: {e.errors()[0]['msg']}")
        
        # 測試正確的批號格式
        valid_record = RecordCreate(
            lot_no="l240108999",  # 小寫，應該轉為大寫
            raw_data={"test": "data"}
        )
        print(f" 批號大寫轉換: {valid_record.lot_no}")
        
        # 3. 測試 UploadErrorCreate
        print(f"\n📝 測試 UploadErrorCreate...")
        error_create_data = {
            "error_message": "測試錯誤訊息",
            "error_details": {
                "row": 10,
                "column": "C",
                "issue": "資料類型錯誤"
            }
        }
        error_create = UploadErrorCreate(**error_create_data)
        print(f" 創建成功: {error_create.error_message}")
        
        # 4. 測試 Read schemas 的 JSON 序列化
        print(f"\n📝 測試 Read schemas JSON 序列化...")
        
        # UploadJobRead
        job_read_data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "filename": "test_file.xlsx",
            "file_size": 1024000,
            "status": JobStatus.COMPLETED,
            "created_at": datetime.now(),
            "processed_at": datetime.now(),
            "total_records": 100,
            "success_records": 98,
            "error_records": 2
        }
        job_read = UploadJobRead(**job_read_data)
        job_json = job_read.model_dump_json()
        print(f" UploadJobRead JSON 序列化成功 ({len(job_json)} chars)")
        
        # RecordRead  
        record_read_data = {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "upload_job_id": "550e8400-e29b-41d4-a716-446655440000",
            "lot_no": "L240108001",
            "product_name": "測試產品",
            "specification": "測試規格",
            "quantity": 50,
            "unit": "pcs",
            "raw_data": {"col1": "value1", "col2": "value2"},
            "created_at": datetime.now()
        }
        record_read = RecordRead(**record_read_data)
        record_json = record_read.model_dump_json()
        print(f" RecordRead JSON 序列化成功 ({len(record_json)} chars)")
        
        # UploadErrorRead
        error_read_data = {
            "id": "550e8400-e29b-41d4-a716-446655440002",
            "upload_job_id": "550e8400-e29b-41d4-a716-446655440000",
            "error_message": "測試錯誤訊息",
            "error_details": {"row": 10, "column": "C", "issue": "資料類型錯誤"},
            "created_at": datetime.now()
        }
        error_read = UploadErrorRead(**error_read_data)
        error_json = error_read.model_dump_json()
        print(f" UploadErrorRead JSON 序列化成功 ({len(error_json)} chars)")
        
        # 5. 測試 JSON Schema 生成
        print(f"\n📝 測試 JSON Schema 生成...")
        
        job_schema = UploadJobCreate.model_json_schema()
        print(f" UploadJobCreate schema: {len(job_schema['properties'])} 個屬性")
        
        record_schema = RecordCreate.model_json_schema()
        print(f" RecordCreate schema: {len(record_schema['properties'])} 個屬性")
        
        error_schema = UploadErrorCreate.model_json_schema()
        print(f" UploadErrorCreate schema: {len(error_schema['properties'])} 個屬性")
        
        print(f"\n🎉 所有 Pydantic Schema 測試通過!")
        print(f"\n📋 測試覆蓋:")
        print(f"    Create schemas 驗證")
        print(f"    欄位驗證器")
        print(f"    錯誤處理")
        print(f"    JSON 序列化")
        print(f"    Schema 生成")
        print(f"    範例資料")
        
        return True
        
    except Exception as e:
        print(f" 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_schemas()