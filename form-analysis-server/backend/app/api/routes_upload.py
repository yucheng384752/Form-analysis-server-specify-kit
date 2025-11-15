"""
檔案上傳路由

處理檔案上傳、驗證和工作建立的 API 端點。
"""

import uuid
import time
from datetime import datetime
from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.upload_job import UploadJob, JobStatus
from app.models.upload_error import UploadError
from app.schemas.upload import FileUploadResponse, UploadErrorResponse
from app.services.validation import file_validation_service, ValidationError

# 獲取日誌記錄器
logger = get_logger(__name__)


# 建立路由器
router = APIRouter(
    tags=["檔案上傳"]
)


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="檔案上傳與驗證",
    description="""
    上傳 CSV 或 Excel 檔案並進行資料驗證
    
    **支援的檔案格式：**
    - CSV (.csv)
    - Excel (.xlsx, .xls)
    
    **lot_no 擷取規則：**
    - P1/P2檔案：從檔案名稱中擷取 (格式：P1_1234567_01.csv 或 P2_1234567_01.csv)
    - P3檔案：從 "P3_No." 欄位中取前9碼作為 lot_no
    
    **驗證規則：**
    - 批號必須符合正規表示式 ^\\d{7}_\\d{2}$
    - P3檔案必須包含 "P3_No." 欄位
    - 其他欄位不進行強制驗證
    
    **回傳內容：**
    - process_id: 處理流程識別碼
    - 統計資訊：總行數、有效行數、無效行數
    - sample_errors: 前10筆驗證錯誤（如果有的話）
    """,
    responses={
        200: {
            "description": "檔案上傳成功，包含驗證結果",
            "content": {
                "application/json": {
                    "example": {
                        "process_id": "123e4567-e89b-12d3-a456-426614174000",
                        "total_rows": 100,
                        "valid_rows": 95,
                        "invalid_rows": 5,
                        "sample_errors": [
                            {
                                "row_index": 2,
                                "field": "lot_no",
                                "error_code": "INVALID_FORMAT",
                                "message": "批號格式錯誤，應為7位數字_2位數字格式，實際值：123456"
                            }
                        ]
                    }
                }
            }
        },
        422: {
            "description": "檔案格式或內容驗證失敗",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_columns": {
                            "summary": "缺少必要欄位",
                            "value": {
                                "detail": "缺少必要欄位：lot_no, quantity"
                            }
                        },
                        "unknown_columns": {
                            "summary": "未知欄位",
                            "value": {
                                "detail": "發現未知欄位：extra_field"
                            }
                        },
                        "file_format": {
                            "summary": "不支援的檔案格式",
                            "value": {
                                "detail": "不支援的檔案格式，僅支援 CSV 和 Excel 檔案"
                            }
                        }
                    }
                }
            }
        },
        413: {
            "description": "檔案過大",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "檔案大小超過限制"
                    }
                }
            }
        },
        500: {
            "description": "伺服器內部錯誤",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "檔案處理時發生未預期的錯誤"
                    }
                }
            }
        }
    }
)
async def upload_file(
    file: UploadFile = File(..., description="要上傳的 CSV 或 Excel 檔案"),
    db: AsyncSession = Depends(get_db)
) -> FileUploadResponse:
    """
    處理檔案上傳和驗證
    
    Args:
        file: 上傳的檔案
        db: 資料庫會話
        
    Returns:
        FileUploadResponse: 上傳結果
        
    Raises:
        HTTPException: 各種驗證或處理錯誤
    """
    start_time = time.time()
    
    logger.info("檔案上傳開始", filename=file.filename if file else None)
    
    try:
        # 1. 檢查檔案是否存在
        if not file or not file.filename:
            logger.warning("上傳失敗：未選擇檔案或檔案名稱為空")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="未選擇檔案或檔案名稱為空"
            )
        
        # 2. 檢查檔案大小（10MB 限制）
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size == 0:
            logger.warning("上傳失敗：檔案內容為空", filename=file.filename)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="檔案內容為空"
            )
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            logger.warning("上傳失敗：檔案超過大小限制", 
                         filename=file.filename, 
                         file_size=file_size,
                         max_size=10*1024*1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="檔案大小超過 10MB 限制"
            )
        
        # 3. 建立上傳工作記錄
        upload_job = UploadJob(
            filename=file.filename,
            status=JobStatus.PENDING,
            file_content=file_content  # 儲存檔案內容以供後續匯入使用
        )
        
        db.add(upload_job)
        await db.commit()
        await db.refresh(upload_job)
        
        logger.info("上傳工作已建立", 
                   process_id=str(upload_job.process_id),
                   filename=file.filename,
                   file_size=file_size)
        
        try:
            # 4. 執行檔案驗證
            logger.info("開始檔案驗證", process_id=str(upload_job.process_id))
            validation_result = file_validation_service.validate_file(
                file_content, 
                file.filename
            )
            
            # 5. 更新上傳工作統計資訊
            upload_job.status = JobStatus.VALIDATED
            upload_job.total_rows = validation_result['total_rows']
            upload_job.valid_rows = validation_result['valid_rows']
            upload_job.invalid_rows = validation_result['invalid_rows']
            
            # 6. 儲存驗證錯誤到資料庫
            upload_errors = []
            for error in validation_result['errors']:
                upload_error = UploadError(
                    job_id=upload_job.id,
                    row_index=error['row_index'],
                    field=error['field'],
                    error_code=error['error_code'],
                    message=error['message']
                )
                upload_errors.append(upload_error)
            
            if upload_errors:
                db.add_all(upload_errors)
            
            await db.commit()
            
            # 7. 準備回應資料
            sample_errors = [
                UploadErrorResponse(
                    row_index=error['row_index'],
                    field=error['field'],
                    error_code=error['error_code'],
                    message=error['message']
                )
                for error in validation_result['sample_errors']
            ]
            
            # 8. 記錄處理時間
            processing_time = time.time() - start_time
            
            logger.info("檔案上傳和驗證完成",
                       process_id=str(upload_job.process_id),
                       filename=file.filename,
                       total_rows=validation_result['total_rows'],
                       valid_rows=validation_result['valid_rows'],
                       invalid_rows=validation_result['invalid_rows'],
                       processing_time=processing_time)
            
            return FileUploadResponse(
                process_id=upload_job.process_id,
                total_rows=validation_result['total_rows'],
                valid_rows=validation_result['valid_rows'],
                invalid_rows=validation_result['invalid_rows'],
                sample_errors=sample_errors
            )
            
        except ValidationError as ve:
            # 驗證錯誤：更新工作狀態但不刪除記錄
            upload_job.status = JobStatus.PENDING  # 保持 PENDING 狀態表示驗證失敗
            await db.commit()
            
            logger.error("檔案驗證失敗",
                        process_id=str(upload_job.process_id),
                        filename=file.filename,
                        error_message=ve.message)
            
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=ve.message
            )
        
        except Exception as e:
            # 其他錯誤：回滾上傳工作建立
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"檔案處理時發生錯誤：{str(e)}"
            )
    
    except HTTPException:
        # 重新拋出 HTTP 例外
        raise
    
    except Exception as e:
        # 捕獲所有其他未處理的例外
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上傳檔案時發生未預期的錯誤：{str(e)}"
        )


@router.get(
    "/upload/{process_id}/status",
    summary="查詢上傳工作狀態",
    description="根據 process_id 查詢上傳工作的處理狀態和結果",
    responses={
        200: {
            "description": "成功取得工作狀態",
            "content": {
                "application/json": {
                    "example": {
                        "process_id": "123e4567-e89b-12d3-a456-426614174000",
                        "status": "VALIDATED",
                        "filename": "data.csv",
                        "total_rows": 100,
                        "valid_rows": 95,
                        "invalid_rows": 5,
                        "created_at": "2024-01-08T10:30:00Z"
                    }
                }
            }
        },
        404: {
            "description": "找不到指定的上傳工作",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "找不到指定的上傳工作"
                    }
                }
            }
        }
    }
)
async def get_upload_status(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    查詢上傳工作狀態
    
    Args:
        process_id: 處理流程識別碼
        db: 資料庫會話
        
    Returns:
        dict: 工作狀態資訊
        
    Raises:
        HTTPException: 找不到工作或其他錯誤
    """
    try:
        # 根據 process_id 查詢上傳工作
        from sqlalchemy import select
        
        result = await db.execute(
            select(UploadJob).where(UploadJob.process_id == process_id)
        )
        upload_job = result.scalar_one_or_none()
        
        if not upload_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="找不到指定的上傳工作"
            )
        
        return {
            "process_id": upload_job.process_id,
            "status": upload_job.status.value,
            "filename": upload_job.filename,
            "total_rows": upload_job.total_rows,
            "valid_rows": upload_job.valid_rows,
            "invalid_rows": upload_job.invalid_rows,
            "created_at": upload_job.created_at.isoformat() if upload_job.created_at else None
        }
        
    except HTTPException:
        raise
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢工作狀態時發生錯誤：{str(e)}"
        )