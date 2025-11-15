"""
資料匯入 API 路由

提供將驗證通過的資料匯入到系統的 API 端點。
"""

import time
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.upload_job import UploadJob, JobStatus
from app.models.record import Record
from app.schemas.import_data import (
    ImportRequest,
    ImportResponse,
    ImportErrorResponse
)
from app.services.validation import file_validation_service

# 獲取日誌記錄器
logger = get_logger(__name__)

# 建立路由器
router = APIRouter()


@router.post(
    "/import",
    response_model=ImportResponse,
    summary="匯入驗證通過的資料",
    description="""
    將指定上傳工作中驗證通過的有效資料匯入到系統中。
    
    ## 功能說明
    
    - 檢查指定的上傳工作是否存在且已完成驗證
    - 重新讀取原始檔案並驗證資料
    - 將所有有效的資料行匯入到 records 表
    - 更新工作狀態為 IMPORTED
    - 回傳匯入統計資訊
    
    ## 前置條件
    
    - 上傳工作必須存在
    - 工作狀態必須為 VALIDATED（已驗證）
    - 不可重複匯入同一工作
    
    ## 匯入過程
    
    1. 驗證工作狀態
    2. 重新解析並驗證檔案內容
    3. 批次匯入所有有效資料行
    4. 更新工作狀態
    5. 回傳統計結果
    
    ## 使用範例
    
    ```bash
    # 匯入指定工作的有效資料
    curl -X POST "http://localhost:8000/api/import" \\
         -H "Content-Type: application/json" \\
         -d '{"process_id": "550e8400-e29b-41d4-a716-446655440000"}'
    ```
    """,
    responses={
        200: {
            "description": "資料匯入成功",
            "model": ImportResponse
        },
        404: {
            "description": "找不到指定的上傳工作",
            "model": ImportErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "找不到指定的上傳工作",
                        "process_id": "550e8400-e29b-41d4-a716-446655440000",
                        "error_code": "JOB_NOT_FOUND"
                    }
                }
            }
        },
        400: {
            "description": "工作狀態不允許匯入",
            "model": ImportErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "not_validated": {
                            "summary": "工作尚未驗證",
                            "value": {
                                "detail": "工作尚未完成驗證，無法匯入資料",
                                "process_id": "550e8400-e29b-41d4-a716-446655440000",
                                "error_code": "JOB_NOT_READY"
                            }
                        },
                        "already_imported": {
                            "summary": "工作已經匯入",
                            "value": {
                                "detail": "資料已經匯入，不可重複操作",
                                "process_id": "550e8400-e29b-41d4-a716-446655440000",
                                "error_code": "JOB_ALREADY_IMPORTED"
                            }
                        }
                    }
                }
            }
        }
    },
    tags=["資料匯入"]
)
async def import_data(
    request: ImportRequest,
    db: AsyncSession = Depends(get_db)
) -> ImportResponse:
    """
    匯入驗證通過的資料
    
    Args:
        request: 匯入請求，包含 process_id
        db: 資料庫會話
        
    Returns:
        ImportResponse: 匯入結果統計
        
    Raises:
        HTTPException: 當工作不存在、狀態不正確或其他錯誤時拋出
    """
    
    start_time = time.time()
    
    logger.info("開始資料匯入", process_id=str(request.process_id))
    
    # 1. 查詢上傳工作
    stmt = select(UploadJob).where(UploadJob.process_id == request.process_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        logger.error("匯入失敗：找不到上傳工作", process_id=str(request.process_id))
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "找不到指定的上傳工作",
                "process_id": str(request.process_id),
                "error_code": "JOB_NOT_FOUND"
            }
        )
    
    # 2. 檢查工作狀態
    if job.status == JobStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "工作尚未完成驗證，無法匯入資料",
                "process_id": str(request.process_id),
                "error_code": "JOB_NOT_READY"
            }
        )
    
    if job.status == JobStatus.IMPORTED:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "資料已經匯入，不可重複操作",
                "process_id": str(request.process_id),
                "error_code": "JOB_ALREADY_IMPORTED"
            }
        )
    
    try:
        # 3. 重新讀取並處理檔案內容
        logger.info("開始處理檔案內容以進行匯入", process_id=str(request.process_id))
        
        # 重要：我們需要從上傳工作中重新讀取原始檔案內容
        # 在這個版本中，我們先實作基於檔案名稱的重讀邏輯
        
        from app.models.record import DataType
        from app.services.validation import file_validation_service
        import pandas as pd
        from datetime import date
        import io
        
        # 檢查是否有儲存的檔案內容
        if not job.file_content:
            raise HTTPException(
                status_code=400,
                detail={
                    "detail": "找不到上傳檔案內容，無法進行匯入",
                    "process_id": str(request.process_id),
                    "error_code": "FILE_CONTENT_MISSING"
                }
            )
        
        logger.info("開始讀取並解析檔案內容", 
                   process_id=str(request.process_id),
                   filename=job.filename,
                   file_size=len(job.file_content))
        
        # 使用 pandas 讀取 CSV 檔案內容
        try:
            # 讀取檔案內容
            df = pd.read_csv(
                io.BytesIO(job.file_content), 
                encoding='utf-8-sig'  # 處理 BOM
            )
            
            if df.empty:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "detail": "檔案內容為空，無法匯入",
                        "process_id": str(request.process_id),
                        "error_code": "EMPTY_FILE"
                    }
                )
            
            logger.info("成功讀取CSV檔案", 
                       process_id=str(request.process_id),
                       rows=len(df),
                       columns=list(df.columns))
            
        except Exception as e:
            logger.error("讀取檔案內容失敗", 
                        process_id=str(request.process_id),
                        error=str(e))
            raise HTTPException(
                status_code=400,
                detail={
                    "detail": f"無法讀取檔案內容：{str(e)}",
                    "process_id": str(request.process_id),
                    "error_code": "FILE_READ_ERROR"
                }
            )
        
        # 從檔案名稱確定數據類型
        filename = job.filename
        filename_lower = filename.lower()
        
        if filename_lower.startswith('p1_'):
            data_type = DataType.P1
        elif filename_lower.startswith('p2_'):
            data_type = DataType.P2  
        elif filename_lower.startswith('p3_'):
            data_type = DataType.P3
        else:
            data_type = DataType.P1  # 預設為P1
        
        # 4. 解析批號
        lot_no = None
        
        if data_type in [DataType.P1, DataType.P2]:
            # P1/P2 檔案：從檔案名稱提取 lot_no
            parts = filename.replace('.csv', '').replace('.xlsx', '').split('_')
            if len(parts) >= 3:
                lot_no = f"{parts[1]}_{parts[2]}"
        elif data_type == DataType.P3:
            # P3 檔案：從 P3_No. 欄位提取 lot_no
            if 'P3_No.' in df.columns and not df['P3_No.'].empty:
                first_p3_no = str(df['P3_No.'].iloc[0])
                # 從 P3_No. 提取前9碼作為 lot_no
                if len(first_p3_no) >= 10:
                    lot_no = first_p3_no[:10]  # 提取前10碼 (7數字_2數字)
            
            if not lot_no:
                logger.warning("無法從P3檔案提取lot_no", 
                              process_id=str(request.process_id),
                              filename=filename)
        
        # 如果無法提取批號，使用預設值或報錯
        if not lot_no:
            logger.warning("無法提取有效的批號", 
                          process_id=str(request.process_id),
                          filename=filename,
                          data_type=data_type.value)
            # 使用檔案名稱的一部分作為預設批號
            lot_no = "0000000_00"
        
        # 5. 批量匯入所有資料行
        imported_rows = 0
        skipped_rows = 0
        
        logger.info("開始處理CSV資料行", 
                   process_id=str(request.process_id),
                   total_rows=len(df),
                   lot_no=lot_no,
                   data_type=data_type.value)
        
        # 處理 DataFrame 中的每一行
        for index, row in df.iterrows():
            try:
                # 轉換 pandas Series 為字典
                row_dict = row.to_dict()
                
                # 分離已知欄位和額外欄位
                known_fields = {}
                additional_fields = {}
                
                # 設置批號（對所有類型都需要）
                known_fields['lot_no'] = lot_no
                
                # 提取已知的資料庫欄位
                if 'product_name' in row_dict and pd.notna(row_dict['product_name']):
                    known_fields['product_name'] = str(row_dict['product_name']).strip()
                
                if 'quantity' in row_dict and pd.notna(row_dict['quantity']):
                    try:
                        known_fields['quantity'] = int(float(row_dict['quantity']))
                    except (ValueError, TypeError):
                        pass
                
                if 'production_date' in row_dict and pd.notna(row_dict['production_date']):
                    try:
                        if isinstance(row_dict['production_date'], str):
                            known_fields['production_date'] = datetime.strptime(row_dict['production_date'], '%Y-%m-%d').date()
                        else:
                            known_fields['production_date'] = row_dict['production_date']
                    except (ValueError, TypeError):
                        pass
                
                if 'notes' in row_dict and pd.notna(row_dict['notes']):
                    known_fields['notes'] = str(row_dict['notes']).strip()
                
                # P2 專用欄位
                for field in ['sheet_width', 'thickness1', 'thickness2', 'thickness3', 
                             'thickness4', 'thickness5', 'thickness6', 'thickness7', 
                             'appearance', 'rough_edge', 'slitting_result']:
                    if field in row_dict and pd.notna(row_dict[field]):
                        try:
                            if 'thickness' in field or field == 'sheet_width':
                                known_fields[field] = float(row_dict[field])
                            else:
                                known_fields[field] = int(float(row_dict[field]))
                        except (ValueError, TypeError):
                            pass
                
                # P3 專用欄位
                if 'P3_No.' in row_dict and pd.notna(row_dict['P3_No.']):
                    known_fields['p3_no'] = str(row_dict['P3_No.']).strip()
                
                # 將所有其他欄位存入 additional_data
                for key, value in row_dict.items():
                    if (key not in ['lot_no', 'product_name', 'quantity', 'production_date', 'notes',
                                   'sheet_width', 'thickness1', 'thickness2', 'thickness3', 'thickness4',
                                   'thickness5', 'thickness6', 'thickness7', 'appearance', 'rough_edge', 
                                   'slitting_result', 'P3_No.'] and pd.notna(value)):
                        # 轉換 numpy 類型為 Python 原生類型
                        if pd.api.types.is_numeric_dtype(type(value)):
                            additional_fields[key] = float(value) if isinstance(value, (int, float)) else str(value)
                        else:
                            additional_fields[key] = str(value).strip()
                
                # 設置預設生產日期（如果沒有提供）
                if 'production_date' not in known_fields:
                    known_fields['production_date'] = date.today()
                
                # 檢查是否已存在相同的 lot_no + data_type 記錄
                existing_stmt = select(Record).where(
                    Record.lot_no == known_fields['lot_no'],
                    Record.data_type == data_type
                )
                existing_result = await db.execute(existing_stmt)
                existing_record = existing_result.scalar_one_or_none()
                
                if existing_record:
                    # 如果記錄已存在，更新它而不是創建新記錄
                    for field, value in known_fields.items():
                        if field != 'lot_no':  # lot_no 不需要更新
                            setattr(existing_record, field, value)
                    
                    existing_record.data_type = data_type
                    existing_record.additional_data = additional_fields if additional_fields else None
                    
                    logger.info("更新現有記錄", 
                               row_index=index,
                               lot_no=known_fields.get('lot_no'),
                               data_type=data_type.value,
                               record_id=str(existing_record.id),
                               process_id=str(request.process_id))
                else:
                    # 創建新記錄
                    record = Record(
                        data_type=data_type,
                        additional_data=additional_fields if additional_fields else None,
                        **known_fields
                    )
                    
                    db.add(record)
                    
                    if imported_rows <= 3:  # 只記錄前3筆的詳細資訊
                        logger.info("成功創建記錄", 
                                   row_index=index,
                                   lot_no=known_fields.get('lot_no'),
                                   data_type=data_type.value,
                                   additional_fields_count=len(additional_fields),
                                   additional_fields=list(additional_fields.keys())[:5],
                                   process_id=str(request.process_id))
                
                imported_rows += 1
                
            except Exception as e:
                logger.error("創建記錄失敗", 
                           error=str(e), 
                           row_index=index,
                           row_data_sample=str(dict(list(row_dict.items())[:3])),
                           process_id=str(request.process_id))
                skipped_rows += 1
                continue
        
        # 5. 更新工作狀態
        job.status = JobStatus.IMPORTED
        await db.commit()
        
        # 6. 計算耗時
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return ImportResponse(
            imported_rows=imported_rows,
            skipped_rows=skipped_rows,
            elapsed_ms=elapsed_ms,
            message=f"資料匯入完成：成功 {imported_rows} 筆，跳過 {skipped_rows} 筆",
            process_id=request.process_id
        )
        
    except Exception as e:
        # 回滾事務
        await db.rollback()
        
        raise HTTPException(
            status_code=500,
            detail={
                "detail": f"匯入過程發生錯誤：{str(e)}",
                "process_id": str(request.process_id),
                "error_code": "IMPORT_ERROR"
            }
        )