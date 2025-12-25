"""
生產追溯查詢 API

提供完整的生產鏈追溯功能：
- 根據 Product_ID 查詢 P3 → P2 → P1 完整生產歷程
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, List, Optional, Any

from app.core.database import get_db
from app.models.record import Record, DataType
from app.services.product_id_generator import parse_product_id, validate_product_id

router = APIRouter(prefix="/api/traceability", tags=["traceability"])


@router.get("/product/{product_id}", response_model=Dict[str, Any])
async def trace_by_product_id(
    product_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    根據 Product_ID 追溯完整生產鏈
    
    查詢順序: P3 → P2 → P1
    - P3: 使用 product_id 直接查詢
    - P2: 使用 P3.lot_no 和 P3.source_winder 查詢
    - P1: 使用 P2.lot_no 查詢
    
    Args:
        product_id: Product ID (格式: YYYY-MM-DD_machine_mold_lot)
        db: 資料庫連線
    
    Returns:
        完整生產鏈資料，包含 P3、P2、P1 資訊
    
    Raises:
        HTTPException: 如果 Product_ID 格式錯誤或查無資料
    
    Example:
        GET /api/traceability/product/2025-09-02_P24_238-2_301
        
        Response:
        {
            "product_id": "2025-09-02_P24_238-2_301",
            "p3": {
                "id": 123,
                "lot_no": "2411012-04",
                "machine_no": "P24",
                "mold_no": "238-2",
                "production_lot": 301,
                "source_winder": 17,
                "production_date": "2025-09-02",
                ...
            },
            "p2": {
                "id": 456,
                "lot_no": "2411012-04",
                "winder_number": 17,
                "material_code": "H8",
                "slitting_machine_number": 1,
                ...
            },
            "p1": {
                "id": 789,
                "lot_no": "2411012-04",
                "material_code": "H8",
                ...
            }
        }
    """
    # 驗證 Product_ID 格式
    is_valid, error_msg = validate_product_id(product_id)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Product_ID 格式錯誤: {error_msg}"
        )
    
    # 步驟 1: 查詢 P3 資料
    p3_query = select(Record).where(
        Record.data_type == DataType.P3,
        Record.product_id == product_id
    )
    p3_result = await db.execute(p3_query)
    p3_record = p3_result.scalar_one_or_none()
    
    if not p3_record:
        raise HTTPException(
            status_code=404,
            detail=f"查無 Product_ID: {product_id}"
        )
    
    # 步驟 2: 使用 P3.lot_no 和 P3.source_winder 查詢對應的 P2
    p2_record = None
    
    # 解析正確的來源收卷機編號
    source_winder = _extract_winder_from_p3(p3_record)
    
    if p3_record.lot_no:
        # 建構查詢條件
        conditions = [
            Record.data_type == DataType.P2,
            Record.lot_no == p3_record.lot_no
        ]
        
        # 如果有收卷機編號，加入查詢條件
        if source_winder is not None:
            conditions.append(Record.winder_number == source_winder)
            
        p2_query = select(Record).where(*conditions)
        p2_result = await db.execute(p2_query)
        p2_record = p2_result.scalar_one_or_none()
        
        # Fallback: 如果指定收卷機找不到，但該批號只有一筆 P2 且無收卷機編號，則使用該筆
        if not p2_record and source_winder is not None:
            fallback_query = select(Record).where(
                Record.data_type == DataType.P2,
                Record.lot_no == p3_record.lot_no
            )
            fallback_result = await db.execute(fallback_query)
            all_p2_records = fallback_result.scalars().all()
            
            if len(all_p2_records) == 1 and all_p2_records[0].winder_number is None:
                p2_record = all_p2_records[0]
    
    # 步驟 3: 使用 P2.lot_no (或 P3.lot_no) 查詢 P1
    p1_record = None
    lot_no_for_p1 = p2_record.lot_no if p2_record else p3_record.lot_no
    
    if lot_no_for_p1:
        p1_query = select(Record).where(
            Record.data_type == DataType.P1,
            Record.lot_no == lot_no_for_p1
        )
        p1_result = await db.execute(p1_query)
        p1_record = p1_result.scalar_one_or_none()
    
    # 組合回應
    response = {
        "product_id": product_id,
        "p3": _record_to_dict(p3_record) if p3_record else None,
        "p2": _record_to_dict(p2_record) if p2_record else None,
        "p1": _record_to_dict(p1_record) if p1_record else None,
        "trace_complete": all([p3_record, p2_record, p1_record]),
        "missing_links": _get_missing_links(p3_record, p2_record, p1_record)
    }
    
    return response


@router.get("/lot/{lot_no}", response_model=Dict[str, Any])
async def trace_by_lot_no(
    lot_no: str,
    db: AsyncSession = Depends(get_db)
):
    """
    根據 Lot_No 查詢相關的所有記錄
    
    回傳該批次的 P1、所有 P2、所有 P3 資料
    
    Args:
        lot_no: 批次編號 (格式: YYYYMDD-WW)
        db: 資料庫連線
    
    Returns:
        該批次的所有相關記錄
    
    Example:
        GET /api/traceability/lot/2411012-04
        
        Response:
        {
            "lot_no": "2411012-04",
            "p1": { ... },
            "p2_records": [ {...}, {...}, ... ],
            "p3_records": [ {...}, {...}, ... ],
            "summary": {
                "total_p2": 5,
                "total_p3": 12
            }
        }
    """
    # 查詢 P1
    p1_query = select(Record).where(
        Record.data_type == DataType.P1,
        Record.lot_no == lot_no
    )
    p1_result = await db.execute(p1_query)
    p1_record = p1_result.scalar_one_or_none()
    
    if not p1_record:
        raise HTTPException(
            status_code=404,
            detail=f"查無 Lot_No: {lot_no}"
        )
    
    # 查詢所有 P2
    p2_query = select(Record).where(
        Record.data_type == DataType.P2,
        Record.lot_no == lot_no
    ).order_by(Record.winder_number)
    p2_result = await db.execute(p2_query)
    p2_records = p2_result.scalars().all()
    
    # 查詢所有 P3
    p3_query = select(Record).where(
        Record.data_type == DataType.P3,
        Record.lot_no == lot_no
    ).order_by(Record.production_lot)
    p3_result = await db.execute(p3_query)
    p3_records = p3_result.scalars().all()
    
    return {
        "lot_no": lot_no,
        "p1": _record_to_dict(p1_record),
        "p2_records": [_record_to_dict(r) for r in p2_records],
        "p3_records": [_record_to_dict(r) for r in p3_records],
        "summary": {
            "total_p2": len(p2_records),
            "total_p3": len(p3_records),
            "p2_winders": sorted([r.winder_number for r in p2_records if r.winder_number]),
            "p3_production_lots": sorted([r.production_lot for r in p3_records if r.production_lot])
        }
    }


@router.get("/winder/{lot_no}/{winder_number}", response_model=Dict[str, Any])
async def trace_by_winder(
    lot_no: str,
    winder_number: int,
    db: AsyncSession = Depends(get_db)
):
    """
    根據 Lot_No 和 Winder 編號查詢追溯鏈
    
    查詢順序: P2 → P1 和 P2 → P3
    
    Args:
        lot_no: 批次編號
        winder_number: 收卷編號 (1-20)
        db: 資料庫連線
    
    Returns:
        該收卷的完整生產資料
    
    Example:
        GET /api/traceability/winder/2411012-04/17
        
        Response:
        {
            "lot_no": "2411012-04",
            "winder_number": 17,
            "p2": { ... },
            "p1": { ... },
            "p3_records": [ {...}, {...} ]
        }
    """
    # 查詢 P2
    p2_query = select(Record).where(
        Record.data_type == DataType.P2,
        Record.lot_no == lot_no,
        Record.winder_number == winder_number
    )
    p2_result = await db.execute(p2_query)
    p2_record = p2_result.scalar_one_or_none()
    
    if not p2_record:
        # Fallback: Check if there is a single P2 record for this lot with no winder number
        # This handles cases where P2 data is missing winder information
        fallback_query = select(Record).where(
            Record.data_type == DataType.P2,
            Record.lot_no == lot_no
        )
        fallback_result = await db.execute(fallback_query)
        all_p2_records = fallback_result.scalars().all()
        
        if len(all_p2_records) == 1 and all_p2_records[0].winder_number is None:
            p2_record = all_p2_records[0]
        else:
            raise HTTPException(
                status_code=404,
                detail=f"查無 P2 記錄: Lot_No={lot_no}, Winder={winder_number}"
            )
    
    # 查詢 P1
    p1_query = select(Record).where(
        Record.data_type == DataType.P1,
        Record.lot_no == lot_no
    )
    p1_result = await db.execute(p1_query)
    p1_record = p1_result.scalar_one_or_none()
    
    # 查詢所有使用此 winder 的 P3 (透過 source_winder)
    p3_query = select(Record).where(
        Record.data_type == DataType.P3,
        Record.lot_no == lot_no,
        Record.source_winder == winder_number
    ).order_by(Record.production_lot)
    p3_result = await db.execute(p3_query)
    p3_records = p3_result.scalars().all()
    
    return {
        "lot_no": lot_no,
        "winder_number": winder_number,
        "p2": _record_to_dict(p2_record),
        "p1": _record_to_dict(p1_record) if p1_record else None,
        "p3_records": [_record_to_dict(r) for r in p3_records],
        "summary": {
            "total_p3_from_this_winder": len(p3_records)
        }
    }


def _extract_winder_from_p3(record: Record) -> Optional[int]:
    """
    從 P3 記錄中解析正確的來源收卷機編號
    邏輯: 找到 P3的 "lot no" 欄位 (在 additional_data 中) -> 7+2+2碼 -> 最後兩碼為卷收機號碼
    """
    if not record or record.data_type != DataType.P3:
        return getattr(record, 'source_winder', None) if record else None
        
    # 嘗試從 additional_data 中找到對應的原始 lot no
    if record.additional_data and isinstance(record.additional_data, dict) and 'rows' in record.additional_data:
        for row in record.additional_data['rows']:
            # 比對 production_lot (lot)
            # 注意：record.production_lot 可能是 int，row['lot'] 也可能是 int 或 str
            if str(row.get('lot')) == str(record.production_lot):
                raw_lot_no = row.get('lot no') # e.g. "2507173_02_17"
                if raw_lot_no and isinstance(raw_lot_no, str) and len(raw_lot_no) >= 2:
                    try:
                        # 取最後兩碼
                        winder_str = raw_lot_no[-2:]
                        return int(winder_str)
                    except ValueError:
                        pass
                        
    return record.source_winder


def _record_to_dict(record: Record) -> Dict[str, Any]:
    """
    將 Record 物件轉換為字典
    
    Args:
        record: Record 模型實例
    
    Returns:
        包含所有欄位的字典
    """
    if not record:
        return None
    
    # 針對 P3 記錄，嘗試解析正確的 source_winder
    source_winder = record.source_winder
    if record.data_type == DataType.P3:
        extracted_winder = _extract_winder_from_p3(record)
        if extracted_winder is not None:
            source_winder = extracted_winder
    
    return {
        "id": record.id,
        "data_type": record.data_type.value if record.data_type else None,
        "lot_no": record.lot_no,
        # "upload_date": record.upload_date.isoformat() if hasattr(record, "upload_date") and record.upload_date else None,
        
        # 新增欄位
        "material_code": record.material_code,
        "slitting_machine_number": record.slitting_machine_number,
        "winder_number": record.winder_number,
        "machine_no": record.machine_no,
        "mold_no": record.mold_no,
        "production_lot": record.production_lot,
        "source_winder": source_winder,
        "product_id": record.product_id,
        
        # JSONB 額外資料
        "additional_data": record.additional_data,
        
        # 時間戳記
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if hasattr(record, "updated_at") and record.updated_at else None,
    }


def _get_missing_links(
    p3_record: Optional[Record],
    p2_record: Optional[Record],
    p1_record: Optional[Record]
) -> List[str]:
    """
    檢查追溯鏈中缺失的環節
    
    Args:
        p3_record: P3 記錄
        p2_record: P2 記錄
        p1_record: P1 記錄
    
    Returns:
        缺失環節的清單
    """
    missing = []
    
    if not p3_record:
        missing.append("P3")
    if not p2_record:
        missing.append("P2")
    if not p1_record:
        missing.append("P1")
    
    return missing
