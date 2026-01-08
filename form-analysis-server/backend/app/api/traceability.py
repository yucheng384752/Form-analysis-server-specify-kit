"""
生產追溯查詢 API

提供完整的生產鏈追溯功能：
- 根據 Product_ID 查詢 P3 → P2 → P1 完整生產歷程
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Dict, List, Optional, Any

from app.core.database import get_db
from app.models.record import Record, DataType
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item
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
    - P3: 使用 product_id 直接查詢 P3Item
    - P2: 使用 P3.lot_no 和 P3.source_winder 查詢 P2Item
    - P1: 使用 P2.lot_no 查詢 Record
    
    Args:
        product_id: Product ID (格式: YYYY-MM-DD_machine_mold_lot)
        db: 資料庫連線
    
    Returns:
        完整生產鏈資料，包含 P3、P2、P1 資訊
    """
    # 驗證 Product_ID 格式
    is_valid, error_msg = validate_product_id(product_id)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Product_ID 格式錯誤: {error_msg}"
        )
    
    # 步驟 1: 查詢 P3 資料 (優先查詢 P3Item)
    p3_query = select(P3Item).options(selectinload(P3Item.record)).where(
        P3Item.product_id == product_id
    )
    p3_result = await db.execute(p3_query)
    p3_item = p3_result.scalar_one_or_none()
    
    p3_data = None
    lot_no = None
    source_winder = None
    
    if p3_item:
        p3_data = _p3_item_to_dict(p3_item)
        lot_no = p3_item.lot_no
        source_winder = p3_item.source_winder
    else:
        # Fallback: 嘗試從舊的 Record 結構查詢 (如果尚未遷移)
        raise HTTPException(
            status_code=404,
            detail=f"查無 Product_ID: {product_id}"
        )
    
    # 步驟 2: 使用 P3.lot_no 和 P3.source_winder 查詢對應的 P2
    p2_data = None
    
    if lot_no:
        # 優先查詢 P2Item
        if source_winder is not None:
            p2_query = select(P2Item).join(Record).where(
                Record.data_type == DataType.P2,
                Record.lot_no == lot_no,
                P2Item.winder_number == source_winder
            ).options(selectinload(P2Item.record))
            
            p2_result = await db.execute(p2_query)
            p2_item = p2_result.scalar_one_or_none()
            
            if p2_item:
                p2_data = _p2_item_to_dict(p2_item)
        
        # 如果找不到 P2Item (可能是舊資料或 winder 不匹配)，嘗試查詢 Record (P2)
        if not p2_data:
            p2_record_query = select(Record).where(
                Record.data_type == DataType.P2,
                Record.lot_no == lot_no
            )
            p2_record_result = await db.execute(p2_record_query)
            p2_records = p2_record_result.scalars().all()
            
            if p2_records:
                # 嘗試從 JSON 中尋找匹配的 winder
                for rec in p2_records:
                    if rec.additional_data and 'rows' in rec.additional_data:
                        for row in rec.additional_data['rows']:
                            # 簡單比對 winder
                            w_val = _extract_winder_from_json(row)
                            if w_val is not None and w_val == source_winder:
                                # 找到匹配的 row，構造一個臨時的 dict
                                p2_data = _record_row_to_dict(rec, row, w_val)
                                break
                    if p2_data: break
                
                # 如果還是找不到，但有 P2 記錄，回傳第一筆的摘要 (標記為不精確)
                if not p2_data and p2_records:
                    p2_data = _record_to_dict(p2_records[0])
                    p2_data['warning'] = "Exact winder match not found"

    # 步驟 3: 使用 P2.lot_no (或 P3.lot_no) 查詢 P1
    p1_data = None
    
    if lot_no:
        p1_query = select(Record).where(
            Record.data_type == DataType.P1,
            Record.lot_no == lot_no
        )
        p1_result = await db.execute(p1_query)
        p1_record = p1_result.scalar_one_or_none()
        
        if p1_record:
            p1_data = _record_to_dict(p1_record)

    # 組合回應
    response = {
        "product_id": product_id,
        "p3": p3_data,
        "p2": p2_data,
        "p1": p1_data,
        "trace_complete": all([p3_data, p2_data, p1_data]),
        "missing_links": _get_missing_links_dict(p3_data, p2_data, p1_data)
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
    """
    # 1. 查詢 P1
    p1_query = select(Record).where(
        Record.data_type == DataType.P1,
        Record.lot_no == lot_no
    )
    p1_result = await db.execute(p1_query)
    p1_record = p1_result.scalar_one_or_none()
    
    p1_data = None
    if p1_record:
        p1_data = _record_to_dict(p1_record)
        if p1_record.additional_data:
            for key, value in p1_record.additional_data.items():
                if key not in p1_data:
                    p1_data[key] = value

    # 2. 查詢 P2
    p2_items_query = select(P2Item).join(Record).where(
        Record.lot_no == lot_no,
        Record.data_type == DataType.P2
    ).options(selectinload(P2Item.record))
    
    p2_items_result = await db.execute(p2_items_query)
    p2_items = p2_items_result.scalars().all()
    
    p2_data_list = []
    if p2_items:
        p2_data_list = [_p2_item_to_dict(item) for item in p2_items]
    else:
        p2_record_query = select(Record).where(
            Record.data_type == DataType.P2,
            Record.lot_no == lot_no
        )
        p2_record_result = await db.execute(p2_record_query)
        p2_records = p2_record_result.scalars().all()
        
        for rec in p2_records:
            if rec.additional_data and 'rows' in rec.additional_data:
                for row in rec.additional_data['rows']:
                    w_val = _extract_winder_from_json(row)
                    if w_val is not None:
                        p2_data_list.append(_record_row_to_dict(rec, row, w_val))
            else:
                p2_data_list.append(_record_to_dict(rec))

    # 3. 查詢 P3
    p3_items_query = select(P3Item).join(Record).where(
        Record.lot_no == lot_no,
        Record.data_type == DataType.P3
    ).options(selectinload(P3Item.record))
    
    p3_items_result = await db.execute(p3_items_query)
    p3_items = p3_items_result.scalars().all()
    
    p3_data_list = []
    if p3_items:
        p3_data_list = [_p3_item_to_dict(item) for item in p3_items]
    else:
        p3_record_query = select(Record).where(
            Record.data_type == DataType.P3,
            Record.lot_no == lot_no
        )
        p3_record_result = await db.execute(p3_record_query)
        p3_records = p3_record_result.scalars().all()
        
        for rec in p3_records:
            if rec.additional_data and 'rows' in rec.additional_data:
                for row in rec.additional_data['rows']:
                    p3_data_list.append(_record_row_to_dict(rec, row, None)) 
            else:
                p3_data_list.append(_record_to_dict(rec))

    return {
        "lot_no": lot_no,
        "p1": p1_data,
        "p2_records": p2_data_list,
        "p3_records": p3_data_list,
        "summary": {
            "total_p2": len(p2_data_list),
            "total_p3": len(p3_data_list)
        }
    }


@router.get("/winder/{lot_no}/{winder_number}", response_model=Dict[str, Any])
async def trace_by_winder(
    lot_no: str,
    winder_number: int,
    db: AsyncSession = Depends(get_db)
):
    """根據 Lot_No 和 Winder 編號查詢追溯鏈"""
    # 查詢 P2
    p2_item_query = select(P2Item).join(Record).where(
        Record.lot_no == lot_no,
        Record.data_type == DataType.P2,
        P2Item.winder_number == winder_number
    ).options(selectinload(P2Item.record))
    
    p2_item_result = await db.execute(p2_item_query)
    p2_item = p2_item_result.scalar_one_or_none()
    
    p2_data = None
    if p2_item:
        p2_data = _p2_item_to_dict(p2_item)
    else:
        # Fallback
        p2_query = select(Record).where(
            Record.data_type == DataType.P2,
            Record.lot_no == lot_no
        )
        p2_result = await db.execute(p2_query)
        p2_records = p2_result.scalars().all()
        
        for rec in p2_records:
            if rec.additional_data and 'rows' in rec.additional_data:
                for row in rec.additional_data['rows']:
                    w_val = _extract_winder_from_json(row)
                    if w_val is not None and w_val == winder_number:
                        p2_data = _record_row_to_dict(rec, row, w_val)
                        break
            if p2_data: break

    if not p2_data:
        raise HTTPException(status_code=404, detail="P2 record not found")

    # 查詢 P1
    p1_query = select(Record).where(
        Record.data_type == DataType.P1,
        Record.lot_no == lot_no
    )
    p1_result = await db.execute(p1_query)
    p1_record = p1_result.scalar_one_or_none()
    p1_data = _record_to_dict(p1_record) if p1_record else None

    # 查詢 P3
    p3_items_query = select(P3Item).join(Record).where(
        Record.lot_no == lot_no,
        Record.data_type == DataType.P3,
        P3Item.source_winder == winder_number
    ).options(selectinload(P3Item.record))
    
    p3_items_result = await db.execute(p3_items_query)
    p3_items = p3_items_result.scalars().all()
    
    p3_data_list = []
    if p3_items:
        p3_data_list = [_p3_item_to_dict(item) for item in p3_items]
    else:
        # Fallback P3
        p3_query = select(Record).where(
            Record.data_type == DataType.P3,
            Record.lot_no == lot_no
        )
        p3_result = await db.execute(p3_query)
        p3_records = p3_result.scalars().all()
        
        # 在記憶體中過濾 source_winder
        for r in p3_records:
            extracted_winder = _extract_winder_from_p3(r)
            if extracted_winder == winder_number:
                p3_data_list.append(_record_to_dict(r))

    return {
        "lot_no": lot_no,
        "winder_number": winder_number,
        "p2": p2_data,
        "p1": p1_data,
        "p3_records": p3_data_list,
        "summary": {
            "total_p3_from_this_winder": len(p3_data_list)
        }
    }


def _p3_item_to_dict(item: P3Item) -> Dict[str, Any]:
    """將 P3Item 轉換為字典"""
    # 準備 row_data 並注入 product_id 以便前端過濾
    row_data = item.row_data.copy() if item.row_data else {}
    if item.product_id:
        row_data['product_id'] = item.product_id

    return {
        "id": item.id,
        "record_id": item.record_id,
        "data_type": DataType.P3.value,
        "display_name": f"P3追蹤 ({item.lot_no})",
        "lot_no": item.lot_no,
        "product_id": item.product_id,
        "machine_no": item.machine_no,
        "mold_no": item.mold_no,
        "production_lot": item.production_lot,
        "source_winder": item.source_winder,
        "production_date": item.production_date.isoformat() if item.production_date else None,
        "specification": item.specification,
        "bottom_tape_lot": item.bottom_tape_lot,
        "product_name": item.record.product_name if item.record else None,
        "quantity": item.record.quantity if item.record else None,
        "notes": item.record.notes if item.record else None,
        "additional_data": {"rows": [row_data]} if row_data else {},
        "created_at": item.created_at.isoformat() if item.created_at else None
    }


def _p2_item_to_dict(item: P2Item) -> Dict[str, Any]:
    """將 P2Item 轉換為字典"""
    record = item.record
    return {
        "id": item.id,
        "record_id": item.record_id,
        "data_type": DataType.P2.value,
        "lot_no": record.lot_no if record else None,
        "winder_number": item.winder_number,
        "material_code": record.material_code if record else None,
        "sheet_width": item.sheet_width,
        "thickness1": item.thickness1,
        "thickness2": item.thickness2,
        "thickness3": item.thickness3,
        "thickness4": item.thickness4,
        "thickness5": item.thickness5,
        "thickness6": item.thickness6,
        "thickness7": item.thickness7,
        "appearance": item.appearance,
        "rough_edge": item.rough_edge,
        "slitting_result": item.slitting_result,
        "additional_data": {"rows": [item.row_data]} if item.row_data else {},
        "created_at": record.created_at.isoformat() if record and record.created_at else None
    }


def _record_to_dict(record: Record) -> Dict[str, Any]:
    """
    將 Record 物件轉換為字典 (僅包含 Record 模型上實際存在的欄位)
    """
    if not record:
        return None
    
    return {
        "id": record.id,
        "data_type": record.data_type.value if record.data_type else None,
        "lot_no": record.lot_no,
        "material_code": record.material_code,
        "production_date": record.production_date.isoformat() if record.production_date else None,
        "product_name": record.product_name,
        "quantity": record.quantity,
        "notes": record.notes,
        "additional_data": record.additional_data,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _extract_winder_from_json(row: Dict[str, Any]) -> Optional[int]:
    """從 JSON row 中提取 winder number"""
    for key, value in row.items():
        normalized_key = str(key).lower().replace(' ', '').replace('_', '')
        if normalized_key in ['windernumber', 'winder', '收卷機', '收卷機編號', '捲收機號碼']:
            try:
                return int(float(value))
            except (ValueError, TypeError):
                pass
    return None


def _record_row_to_dict(record: Record, row: Dict[str, Any], winder: Optional[int]) -> Dict[str, Any]:
    """將 Record 的一行 JSON 轉換為類似 Item 的字典"""
    base = _record_to_dict(record)
    base['additional_data'] = {'rows': [row]}
    if winder is not None:
        base['winder_number'] = winder
    return base


def _get_missing_links_dict(
    p3_data: Optional[Dict],
    p2_data: Optional[Dict],
    p1_data: Optional[Dict]
) -> List[str]:
    """檢查追溯鏈中缺失的環節"""
    missing = []
    if not p3_data:
        missing.append("P3")
    if not p2_data:
        missing.append("P2")
    if not p1_data:
        missing.append("P1")
    return missing


def _extract_winder_from_p3(record: Record) -> Optional[int]:
    """
    從 P3 記錄中解析正確的來源收卷機編號
    邏輯: 找到 P3的 "lot no" 欄位 (在 additional_data 中) -> 7+2+2碼 -> 最後兩碼為卷收機號碼
    """
    if not record or record.data_type != DataType.P3:
        return None
        
    # 嘗試從 additional_data 中找到對應的原始 lot no
    if record.additional_data and isinstance(record.additional_data, dict) and 'rows' in record.additional_data:
        for row in record.additional_data['rows']:
            # 嘗試找 lot no 欄位
            raw_lot_no = row.get('lot no') or row.get('Lot No') or row.get('P3_No.')
            if raw_lot_no and isinstance(raw_lot_no, str) and len(raw_lot_no) >= 2:
                try:
                    # 假設格式為 XXXXXXX_XX_WW (批號_機台_收卷)
                    # 或者 XXXXXXX_XX (批號_收卷)
                    parts = raw_lot_no.split('_')
                    if len(parts) >= 3:
                        # 取最後一部分作為 winder
                        winder_str = parts[-1]
                        # 如果最後一部分是 copy 之類的，忽略
                        if 'copy' in winder_str:
                            winder_str = parts[-2]
                            
                        if winder_str.isdigit():
                            return int(winder_str)
                except ValueError:
                    pass
                        
    return None

