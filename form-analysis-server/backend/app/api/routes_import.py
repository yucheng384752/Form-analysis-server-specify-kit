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
from app.models.p3_item import P3Item
from app.schemas.import_data import (
    ImportRequest,
    ImportResponse,
    ImportErrorResponse
)
from app.services.validation import file_validation_service
from app.services.production_date_extractor import production_date_extractor

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
        
        # 從檔案名稱確定資料類型
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
            # P3 檔案：支援新舊兩種格式
            # 1. 新格式：從 "lot no" 欄位提取（優先）
            # 2. 舊格式：從 "P3_No." 欄位提取
            
            if 'lot no' in df.columns and not df['lot no'].empty:
                # 新格式：直接從 "lot no" 欄位讀取
                first_lot_no = str(df['lot no'].iloc[0]).strip()
                
                # 正規化批號（支援 7+2+2 或更多段格式，自動截取前 9 碼）
                import re
                flexible_pattern = re.compile(r'^(\d{7}_\d{2})(?:_.+)?$')
                match = flexible_pattern.match(first_lot_no)
                if match:
                    lot_no = match.group(1)  # 提取前 9 碼
                else:
                    lot_no = first_lot_no  # 如果不符合格式，保留原值讓驗證處理
                    
            elif 'P3_No.' in df.columns and not df['P3_No.'].empty:
                # 舊格式：從 P3_No. 欄位提取前 9 碼
                first_p3_no = str(df['P3_No.'].iloc[0])
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
        
        # 5. 批量匯入資料
        imported_rows = 0
        skipped_rows = 0
        
        logger.info("開始處理CSV資料行", 
                   process_id=str(request.process_id),
                   total_rows=len(df),
                   lot_no=lot_no,
                   data_type=data_type.value)
        
        # P2 特殊處理：父子表結構（Record + P2Items）
        if data_type == DataType.P2:
            try:
                from app.models.p2_item import P2Item
                
                # 1. 準備資料
                all_rows = []
                for index, row in df.iterrows():
                    row_dict = row.to_dict()
                    cleaned_row = {k: (v if pd.notna(v) else None) for k, v in row_dict.items()}
                    all_rows.append(cleaned_row)
                
                # 2. 檢查或創建父記錄
                existing_stmt = select(Record).where(
                    Record.lot_no == lot_no,
                    Record.data_type == data_type
                )
                existing_result = await db.execute(existing_stmt)
                existing_record = existing_result.scalar_one_or_none()
                
                # 提取生產日期
                production_date = production_date_extractor.extract_production_date(
                    row_data={'additional_data': all_rows[0] if all_rows else {}},
                    data_type=data_type.value
                ) or date.today()
                
                if existing_record:
                    # 更新現有記錄
                    existing_record.additional_data = {'rows': all_rows}
                    existing_record.production_date = production_date
                    # 清除舊的 P2Items (CASCADE 會自動處理，但顯式刪除更安全)
                    if existing_record.p2_items:
                        for old_item in existing_record.p2_items:
                            await db.delete(old_item)
                else:
                    # 創建新記錄
                    existing_record = Record(
                        lot_no=lot_no,
                        data_type=data_type,
                        production_date=production_date,
                        additional_data={'rows': all_rows}
                    )
                    db.add(existing_record)
                    await db.flush() # 獲取 ID
                
                # 3. 創建 P2Items
                for winder_index, row_data in enumerate(all_rows, start=1):
                    # 處理數值轉換 helper
                    def get_float(key):
                        val = row_data.get(key)
                        try:
                            return float(val) if val is not None else None
                        except (ValueError, TypeError):
                            return None
                            
                    def get_int_or_status(key):
                        val = row_data.get(key)
                        if val == 'OK': return 1
                        if val == 'NG': return 0
                        try:
                            return int(float(val)) if val is not None else None
                        except (ValueError, TypeError):
                            return None

                    p2_item = P2Item(
                        record_id=existing_record.id,
                        winder_number=winder_index,
                        sheet_width=get_float('Sheet Width(mm)'),
                        thickness1=get_float('Thicknessss1(μm)'),
                        thickness2=get_float('Thicknessss2(μm)'),
                        thickness3=get_float('Thicknessss3(μm)'),
                        thickness4=get_float('Thicknessss4(μm)'),
                        thickness5=get_float('Thicknessss5(μm)'),
                        thickness6=get_float('Thicknessss6(μm)'),
                        thickness7=get_float('Thicknessss7(μm)'),
                        appearance=get_int_or_status('Appearance'),
                        rough_edge=get_int_or_status('rough edge'),
                        slitting_result=get_int_or_status('Slitting Result'),
                        row_data=row_data
                    )
                    db.add(p2_item)
                
                imported_rows = len(all_rows)
                logger.info("P2資料匯入完成",
                           lot_no=lot_no,
                           total_winders=imported_rows,
                           record_id=str(existing_record.id))
                
            except Exception as e:
                logger.error("處理P2資料失敗",
                           error=str(e),
                           lot_no=lot_no,
                           process_id=str(request.process_id))
                raise HTTPException(
                    status_code=500,
                    detail={
                        "detail": f"處理P2資料失敗：{str(e)}",
                        "process_id": str(request.process_id),
                        "error_code": "IMPORT_ERROR"
                    }
                )
        
        # P3 特殊處理：將多行資料合併為單一記錄
        elif data_type == DataType.P3:
            try:
                # 將所有行轉換為列表存入 additional_data
                all_rows = []
                for index, row in df.iterrows():
                    row_dict = row.to_dict()
                    # 清理 NaN 值
                    cleaned_row = {k: (v if pd.notna(v) else None) for k, v in row_dict.items()}
                    all_rows.append(cleaned_row)

                # 取第一列作為代表（P2/P3 合併為單一記錄時，用於填充可檢索欄位）
                first_row = all_rows[0] if all_rows else {}
                
                # 檢查是否已存在相同的 lot_no + data_type 記錄
                existing_stmt = select(Record).where(
                    Record.lot_no == lot_no,
                    Record.data_type == data_type
                )
                existing_result = await db.execute(existing_stmt)
                existing_record = existing_result.scalar_one_or_none()
                
                if existing_record:
                    # 更新現有記錄
                    # 提取生產日期
                    production_date = production_date_extractor.extract_production_date(
                        row_data={'additional_data': all_rows[0] if all_rows else {}},
                        data_type=data_type.value
                    ) or date.today()  # 如果提取失敗，fallback 到當前日期
                    
                    existing_record.additional_data = {'rows': all_rows}
                    existing_record.production_date = production_date

                    # P3：同步填充可檢索欄位（避免只存在 JSON 內造成欄位全為 NULL）
                    if data_type == DataType.P3 and first_row:
                        machine_no_val = (
                            first_row.get('Machine NO')
                            or first_row.get('Machine No')
                            or first_row.get('Machine')
                            or first_row.get('machine_no')
                            or first_row.get('machine')
                        )
                        mold_no_val = (
                            first_row.get('Mold NO')
                            or first_row.get('Mold No')
                            or first_row.get('Mold')
                            or first_row.get('mold_no')
                            or first_row.get('mold')
                        )
                        specification_val = (
                            first_row.get('Specification')
                            or first_row.get('specification')
                            or first_row.get('規格')
                            or first_row.get('Spec')
                        )
                        bottom_tape_val = (
                            first_row.get('Bottom Tape')
                            or first_row.get('bottom tape')
                            or first_row.get('Bottom Tape LOT')
                            or first_row.get('下膠編號')
                            or first_row.get('下膠')
                        )

                        production_lot_val = first_row.get('lot')
                        try:
                            production_lot_val = int(production_lot_val) if production_lot_val is not None else None
                        except (ValueError, TypeError):
                            production_lot_val = None

                        if machine_no_val:
                            existing_record.machine_no = str(machine_no_val).strip()
                        if mold_no_val:
                            existing_record.mold_no = str(mold_no_val).strip()
                        if specification_val:
                            existing_record.specification = str(specification_val).strip()
                        if bottom_tape_val:
                            existing_record.bottom_tape_lot = str(bottom_tape_val).strip()
                        if production_lot_val is not None:
                            existing_record.production_lot = production_lot_val
                        
                        # 從 lot_no 提取卷收機編號（最後兩碼）
                        if lot_no and len(lot_no) >= 2:
                            try:
                                # lot_no 格式：XXXXXXX_XX_YY，提取最後兩碼 YY
                                # 或者直接從字串最後兩位提取
                                last_two = lot_no[-2:]
                                if last_two.isdigit():
                                    existing_record.source_winder = int(last_two)
                            except (ValueError, AttributeError):
                                pass  # 如果無法提取，保持原值

                        # product_id（若必要欄位齊全且尚未有值）
                        if (
                            not existing_record.product_id
                            and existing_record.machine_no
                            and existing_record.mold_no
                            and existing_record.production_lot is not None
                            and existing_record.production_date
                        ):
                            from app.services.product_id_generator import generate_product_id
                            existing_record.product_id = generate_product_id(
                                existing_record.production_date,
                                existing_record.machine_no,
                                existing_record.mold_no,
                                existing_record.production_lot,
                            )
                        
                        # 寫入 P3 明細項目子表
                        # 先刪除舊的明細項目（CASCADE 會自動處理）
                        if existing_record.p3_items:
                            for old_item in existing_record.p3_items:
                                await db.delete(old_item)
                        
                        # 為每一行創建 P3Item
                        for row_no, row_data in enumerate(all_rows, start=1):
                            # 提取 P3_No. 來組成 product_id
                            p3_no_raw = (
                                row_data.get('P3_No.')
                                or row_data.get('P3 No.')
                                or row_data.get('p3_no')
                                or row_data.get('P3NO')
                            )
                            
                            if p3_no_raw:
                                # P3_No. 格式：XXXXXXXX_XX_YY (lot_no_機台_批次)
                                # 組合成 product_id: YYYYMMDD_XX_YY_Z (日期_機台_模具_批次)
                                p3_no_str = str(p3_no_raw).strip()
                                parts = p3_no_str.split('_')
                                
                                if len(parts) >= 3:
                                    machine_from_p3 = parts[1]  # 機台編號
                                    lot_from_p3 = parts[2]      # 批次
                                    
                                    # 組成完整的 product_id
                                    if existing_record.production_date and existing_record.mold_no:
                                        date_str = existing_record.production_date.strftime('%Y%m%d')
                                        item_product_id = f"{date_str}_{machine_from_p3}_{existing_record.mold_no}_{lot_from_p3}"
                                    else:
                                        item_product_id = None
                                else:
                                    item_product_id = None
                            else:
                                item_product_id = None
                            
                            # 提取其他欄位
                            item_lot_no = row_data.get('lot') or row_data.get('LOT') or row_data.get('Lot')
                            item_machine_no = (
                                row_data.get('Machine NO')
                                or row_data.get('Machine No')
                                or row_data.get('Machine')
                                or row_data.get('machine_no')
                                or row_data.get('machine')
                            )
                            item_mold_no = (
                                row_data.get('Mold NO')
                                or row_data.get('Mold No')
                                or row_data.get('Mold')
                                or row_data.get('mold_no')
                                or row_data.get('mold')
                            )
                            item_specification = (
                                row_data.get('Specification')
                                or row_data.get('specification')
                                or row_data.get('規格')
                                or row_data.get('Spec')
                            )
                            item_bottom_tape = (
                                row_data.get('Bottom Tape')
                                or row_data.get('bottom tape')
                                or row_data.get('Bottom Tape LOT')
                                or row_data.get('下膠編號')
                                or row_data.get('下膠')
                            )
                            
                            p3_item = P3Item(
                                record_id=existing_record.id,
                                product_id=item_product_id,
                                lot_no=str(item_lot_no).strip() if item_lot_no else None,
                                machine_no=str(item_machine_no).strip() if item_machine_no else None,
                                mold_no=str(item_mold_no).strip() if item_mold_no else None,
                                specification=str(item_specification).strip() if item_specification else None,
                                bottom_tape_lot=str(item_bottom_tape).strip() if item_bottom_tape else None,
                                row_no=row_no,
                                row_data=row_data
                            )
                            db.add(p3_item)
                    
                    logger.info("更新現有P2/P3記錄",
                               lot_no=lot_no,
                               data_type=data_type.value,
                               rows_count=len(all_rows),
                               record_id=str(existing_record.id),
                               process_id=str(request.process_id))
                else:
                    # 創建新記錄
                    # 提取生產日期
                    production_date = production_date_extractor.extract_production_date(
                        row_data={'additional_data': all_rows[0] if all_rows else {}},
                        data_type=data_type.value
                    ) or date.today()  # 如果提取失敗，fallback 到當前日期

                    record_kwargs = {
                        'lot_no': lot_no,
                        'data_type': data_type,
                        'production_date': production_date,
                        'additional_data': {'rows': all_rows}
                    }

                    # P3：同步填充可檢索欄位
                    if data_type == DataType.P3 and first_row:
                        machine_no_val = (
                            first_row.get('Machine NO')
                            or first_row.get('Machine No')
                            or first_row.get('Machine')
                            or first_row.get('machine_no')
                            or first_row.get('machine')
                        )
                        mold_no_val = (
                            first_row.get('Mold NO')
                            or first_row.get('Mold No')
                            or first_row.get('Mold')
                            or first_row.get('mold_no')
                            or first_row.get('mold')
                        )
                        specification_val = (
                            first_row.get('Specification')
                            or first_row.get('specification')
                            or first_row.get('規格')
                            or first_row.get('Spec')
                        )
                        bottom_tape_val = (
                            first_row.get('Bottom Tape')
                            or first_row.get('bottom tape')
                            or first_row.get('Bottom Tape LOT')
                            or first_row.get('下膠編號')
                            or first_row.get('下膠')
                        )

                        production_lot_val = first_row.get('lot')
                        try:
                            production_lot_val = int(production_lot_val) if production_lot_val is not None else None
                        except (ValueError, TypeError):
                            production_lot_val = None

                        if machine_no_val:
                            record_kwargs['machine_no'] = str(machine_no_val).strip()
                        if mold_no_val:
                            record_kwargs['mold_no'] = str(mold_no_val).strip()
                        if specification_val:
                            record_kwargs['specification'] = str(specification_val).strip()
                        if bottom_tape_val:
                            record_kwargs['bottom_tape_lot'] = str(bottom_tape_val).strip()
                        if production_lot_val is not None:
                            record_kwargs['production_lot'] = production_lot_val
                        
                        # 從 lot_no 提取卷收機編號（最後兩碼）
                        if lot_no and len(lot_no) >= 2:
                            try:
                                # lot_no 格式：XXXXXXX_XX_YY，提取最後兩碼 YY
                                last_two = lot_no[-2:]
                                if last_two.isdigit():
                                    record_kwargs['source_winder'] = int(last_two)
                            except (ValueError, AttributeError):
                                pass  # 如果無法提取，跳過

                        # product_id（若必要欄位齊全）
                        if (
                            record_kwargs.get('machine_no')
                            and record_kwargs.get('mold_no')
                            and record_kwargs.get('production_lot') is not None
                            and record_kwargs.get('production_date')
                        ):
                            from app.services.product_id_generator import generate_product_id
                            record_kwargs['product_id'] = generate_product_id(
                                record_kwargs['production_date'],
                                record_kwargs['machine_no'],
                                record_kwargs['mold_no'],
                                record_kwargs['production_lot'],
                            )

                    record = Record(**record_kwargs)
                    db.add(record)
                    await db.flush()  # 確保 record.id 可用
                    
                    # P3：寫入明細項目子表
                    if data_type == DataType.P3:
                        for row_no, row_data in enumerate(all_rows, start=1):
                            # 提取 P3_No. 來組成 product_id
                            p3_no_raw = (
                                row_data.get('P3_No.')
                                or row_data.get('P3 No.')
                                or row_data.get('p3_no')
                                or row_data.get('P3NO')
                            )
                            
                            if p3_no_raw:
                                # P3_No. 格式：XXXXXXXX_XX_YY (lot_no_機台_批次)
                                # 組合成 product_id: YYYYMMDD_XX_YY_Z (日期_機台_模具_批次)
                                p3_no_str = str(p3_no_raw).strip()
                                parts = p3_no_str.split('_')
                                
                                if len(parts) >= 3:
                                    machine_from_p3 = parts[1]  # 機台編號
                                    lot_from_p3 = parts[2]      # 批次
                                    
                                    # 組成完整的 product_id
                                    if record.production_date and record.mold_no:
                                        date_str = record.production_date.strftime('%Y%m%d')
                                        item_product_id = f"{date_str}_{machine_from_p3}_{record.mold_no}_{lot_from_p3}"
                                    else:
                                        item_product_id = None
                                else:
                                    item_product_id = None
                            else:
                                item_product_id = None
                            
                            # 提取其他欄位
                            item_lot_no = row_data.get('lot') or row_data.get('LOT') or row_data.get('Lot')
                            item_machine_no = (
                                row_data.get('Machine NO')
                                or row_data.get('Machine No')
                                or row_data.get('Machine')
                                or row_data.get('machine_no')
                                or row_data.get('machine')
                            )
                            item_mold_no = (
                                row_data.get('Mold NO')
                                or row_data.get('Mold No')
                                or row_data.get('Mold')
                                or row_data.get('mold_no')
                                or row_data.get('mold')
                            )
                            item_specification = (
                                row_data.get('Specification')
                                or row_data.get('specification')
                                or row_data.get('規格')
                                or row_data.get('Spec')
                            )
                            item_bottom_tape = (
                                row_data.get('Bottom Tape')
                                or row_data.get('bottom tape')
                                or row_data.get('Bottom Tape LOT')
                                or row_data.get('下膠編號')
                                or row_data.get('下膠')
                            )
                            
                            p3_item = P3Item(
                                record_id=record.id,
                                product_id=item_product_id,
                                lot_no=str(item_lot_no).strip() if item_lot_no else None,
                                machine_no=str(item_machine_no).strip() if item_machine_no else None,
                                mold_no=str(item_mold_no).strip() if item_mold_no else None,
                                specification=str(item_specification).strip() if item_specification else None,
                                bottom_tape_lot=str(item_bottom_tape).strip() if item_bottom_tape else None,
                                row_no=row_no,
                                row_data=row_data
                            )
                            db.add(p3_item)
                    
                    logger.info("創建新P2/P3記錄",
                               lot_no=lot_no,
                               data_type=data_type.value,
                               rows_count=len(all_rows),
                               process_id=str(request.process_id))
                
                imported_rows = len(all_rows)
                
            except Exception as e:
                logger.error("處理P2/P3資料失敗",
                           error=str(e),
                           lot_no=lot_no,
                           data_type=data_type.value,
                           process_id=str(request.process_id))
                raise HTTPException(
                    status_code=500,
                    detail={
                        "detail": f"處理{data_type.value}資料失敗：{str(e)}",
                        "process_id": str(request.process_id),
                        "error_code": "IMPORT_ERROR"
                    }
                )
        
        # P1 處理：每一行作為獨立記錄
        elif data_type == DataType.P1:
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
                    
                    # 使用 production_date_extractor 提取日期
                    extracted_date = production_date_extractor.extract_production_date(
                        row_data={'additional_data': row_dict},
                        data_type=DataType.P1.value
                    )
                    if extracted_date:
                        known_fields['production_date'] = extracted_date
                    elif 'production_date' in row_dict and pd.notna(row_dict['production_date']):
                        # 保留原有的 fallback 邏輯，以防 extractor 失敗但欄位存在
                        try:
                            if isinstance(row_dict['production_date'], str):
                                known_fields['production_date'] = datetime.strptime(row_dict['production_date'], '%Y-%m-%d').date()
                            else:
                                known_fields['production_date'] = row_dict['production_date']
                        except (ValueError, TypeError):
                            pass
                    
                    if 'notes' in row_dict and pd.notna(row_dict['notes']):
                        known_fields['notes'] = str(row_dict['notes']).strip()
                    
                    # 將所有其他欄位存入 additional_data
                    for key, value in row_dict.items():
                        if (key not in ['lot_no', 'product_name', 'quantity', 'production_date', 'notes'] 
                            and pd.notna(value)):
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
                        
                        logger.info("更新現有P1記錄", 
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
                            logger.info("成功創建P1記錄", 
                                       row_index=index,
                                       lot_no=known_fields.get('lot_no'),
                                       data_type=data_type.value,
                                       additional_fields_count=len(additional_fields),
                                       additional_fields=list(additional_fields.keys())[:5],
                                       process_id=str(request.process_id))
                    
                    imported_rows += 1
                    
                except Exception as e:
                    logger.error("處理P1記錄失敗", 
                               error=str(e), 
                               row_index=index,
                               process_id=str(request.process_id))
                    skipped_rows += 1
                    continue
        
        # 6. 更新工作狀態
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