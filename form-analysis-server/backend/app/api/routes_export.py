"""
資料匯出 API 路由

提供匯出驗證錯誤資料為 CSV 格式的 API 端點。
"""

import io
import csv
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.upload_job import UploadJob
from app.models.upload_error import UploadError

# 建立路由器
router = APIRouter()


@router.get(
    "/errors.csv",
    summary="匯出錯誤資料 CSV",
    description="""
    動態產生並下載指定上傳工作的所有驗證錯誤資料 CSV 檔案。
    
    ## 功能說明
    
    - 根據 process_id 查詢對應的驗證錯誤
    - 即時產生 CSV 格式的錯誤報告
    - 包含完整的錯誤詳細資訊
    - 適合用於錯誤修正和問題分析
    
    ## CSV 格式
    
    檔案包含以下欄位：
    - **row_index**: 錯誤發生的行號（從1開始，不包含標題行）
    - **field**: 發生錯誤的欄位名稱
    - **error_code**: 錯誤類型代碼
    - **message**: 詳細的錯誤描述訊息
    
    ## 使用範例
    
    ```bash
    # 下載錯誤報告 CSV
    curl -o errors.csv "http://localhost:8000/api/errors.csv?process_id=550e8400-e29b-41d4-a716-446655440000"
    
    # 在瀏覽器中直接下載
    http://localhost:8000/api/errors.csv?process_id=550e8400-e29b-41d4-a716-446655440000
    ```
    
    ## 回傳檔案範例
    
    ```csv
    row_index,field,error_code,message
    5,lot_no,INVALID_FORMAT,批號格式錯誤，應為7位數字_2位數字格式，實際值：123456_01
    8,product_name,REQUIRED_FIELD,產品名稱不能為空
    12,quantity,INVALID_VALUE,數量必須為非負整數，實際值：-50
    15,production_date,INVALID_FORMAT,生產日期格式錯誤，應為YYYY-MM-DD格式，實際值：2024/01/15
    ```
    """,
    responses={
        200: {
            "description": "成功產生 CSV 檔案",
            "content": {
                "text/csv": {
                    "example": "row_index,field,error_code,message\n5,lot_no,INVALID_FORMAT,批號格式錯誤\n8,product_name,REQUIRED_FIELD,產品名稱不能為空"
                }
            },
            "headers": {
                "Content-Disposition": {
                    "description": "CSV 檔案下載名稱",
                    "schema": {"type": "string"}
                }
            }
        },
        404: {
            "description": "找不到指定的上傳工作",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "找不到指定的上傳工作",
                        "process_id": "550e8400-e29b-41d4-a716-446655440000"
                    }
                }
            }
        },
        422: {
            "description": "參數驗證錯誤",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "uuid_parsing",
                                "loc": ["query", "process_id"],
                                "msg": "Input should be a valid UUID",
                                "input": "invalid-uuid"
                            }
                        ]
                    }
                }
            }
        }
    },
    tags=["資料匯出"]
)
async def export_errors_csv(
    process_id: UUID = Query(
        ...,
        description="處理流程識別碼",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    ),
    db: AsyncSession = Depends(get_db)
) -> Response:
    """
    匯出驗證錯誤為 CSV 格式
    
    Args:
        process_id: 處理流程識別碼
        db: 資料庫會話
        
    Returns:
        Response: CSV 格式的錯誤報告檔案
        
    Raises:
        HTTPException: 當找不到指定工作時拋出 404 錯誤
    """
    
    # 1. 查詢上傳工作是否存在
    job_stmt = select(UploadJob).where(UploadJob.process_id == process_id)
    job_result = await db.execute(job_stmt)
    job = job_result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "找不到指定的上傳工作",
                "process_id": str(process_id)
            }
        )
    
    # 2. 查詢所有錯誤項目
    errors_stmt = (
        select(UploadError)
        .where(UploadError.job_id == job.id)
        .order_by(UploadError.row_index, UploadError.field)
    )
    errors_result = await db.execute(errors_stmt)
    errors = errors_result.scalars().all()
    
    # 3. 產生 CSV 內容
    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer)
    
    # 寫入標題行
    csv_writer.writerow(["row_index", "field", "error_code", "message"])
    
    # 寫入錯誤資料
    for error in errors:
        csv_writer.writerow([
            error.row_index + 1,  # 轉換為從1開始的行號
            error.field,
            error.error_code,
            error.message
        ])
    
    # 4. 準備 CSV 內容
    csv_content = csv_buffer.getvalue()
    csv_buffer.close()
    
    # 5. 產生檔案名稱
    filename = f"errors_{process_id}.csv"
    
    # 6. 回傳 CSV 檔案
    return Response(
        content=csv_content.encode('utf-8-sig'),  # 使用 UTF-8 BOM 確保中文正確顯示
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )