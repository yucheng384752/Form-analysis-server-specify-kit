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
from app.api.deps import get_current_tenant
from app.models.core.tenant import Tenant
from app.models.record import Record, DataType
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.services.product_id_generator import parse_product_id, validate_product_id
from app.utils.normalization import normalize_lot_no

router = APIRouter(prefix="/api/traceability", tags=["traceability"])


@router.get("/product/{product_id}", response_model=Dict[str, Any])
async def trace_by_product_id(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
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
    
    # 步驟 1: 查詢 P3 資料 (優先查詢舊的 P3Item)
    p3_query = select(P3Item).options(selectinload(P3Item.record)).where(
        P3Item.product_id == product_id
    )
    p3_result = await db.execute(p3_query)
    p3_item = p3_result.scalar_one_or_none()
    
    p3_data = None
    lot_no = None  # base lot for P1/P2 lookup
    source_winder = None
    
    if p3_item:
        p3_data = _p3_item_to_dict(p3_item)
        # Prefer DB columns; if missing, derive from row payload
        lot_no = p3_item.lot_no
        source_winder = p3_item.source_winder

        payload = _get_first_row_payload(p3_data)
        base_lot, parsed_winder = _extract_base_lot_and_winder_from_p3_payload(payload)
        if base_lot:
            lot_no = base_lot
            # also reflect base lot in returned p3 payload for frontend
            p3_data['lot_no'] = base_lot
        if source_winder is None and parsed_winder is not None:
            source_winder = parsed_winder
            p3_data['source_winder'] = parsed_winder
    else:
        # Fallback (V2): 從 p3_records 取出對應資料
        p3_v2 = None

        # 1) Exact match by product_id
        p3_v2_stmt = select(P3Record).where(
            P3Record.tenant_id == current_tenant.id,
            P3Record.product_id == product_id,
        )
        p3_v2_result = await db.execute(p3_v2_stmt)
        p3_v2 = p3_v2_result.scalar_one_or_none()

        # 2) Prefix match by base product_id (handles suffix like _1)
        if not p3_v2:
            parts = product_id.split('_')
            if len(parts) >= 4:
                base_product_id = '_'.join(parts[:4])
                p3_v2_prefix_stmt = select(P3Record).where(
                    P3Record.tenant_id == current_tenant.id,
                    P3Record.product_id.ilike(f"{base_product_id}%"),
                )
                p3_v2_prefix_result = await db.execute(p3_v2_prefix_stmt)
                p3_v2 = p3_v2_prefix_result.scalar_one_or_none()

        # 3) Component match by parsed product_id (works even if stored product_id used a different separator previously)
        if not p3_v2:
            try:
                parsed = parse_product_id(product_id)
                prod_yyyymmdd = int(parsed['production_date'].strftime('%Y%m%d'))
                machine_no = str(parsed['machine_no']).strip() if parsed.get('machine_no') else None
                mold_no = str(parsed['mold_no']).strip() if parsed.get('mold_no') else None
                if machine_no and mold_no:
                    p3_v2_comp_stmt = select(P3Record).where(
                        P3Record.tenant_id == current_tenant.id,
                        P3Record.production_date_yyyymmdd == prod_yyyymmdd,
                        P3Record.machine_no == machine_no,
                        P3Record.mold_no == mold_no,
                    )
                    p3_v2_comp_result = await db.execute(p3_v2_comp_stmt)
                    p3_v2 = p3_v2_comp_result.scalar_one_or_none()
            except Exception:
                p3_v2 = None

        if not p3_v2:
            raise HTTPException(
                status_code=404,
                detail=f"查無 Product_ID: {product_id}"
            )

        p3_data = _p3_record_to_dict(p3_v2)
        lot_no = p3_v2.lot_no_raw
        source_winder = _extract_source_winder_from_v2_extras(p3_v2.extras)

        payload = _get_first_row_payload(p3_data)
        base_lot, parsed_winder = _extract_base_lot_and_winder_from_p3_payload(payload)
        if base_lot:
            lot_no = base_lot
            p3_data['lot_no'] = base_lot
        if source_winder is None and parsed_winder is not None:
            source_winder = parsed_winder
            p3_data['source_winder'] = parsed_winder
    
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

    # V2 fallback: 舊路徑有 P3 但 P2 沒找到時，嘗試從 p2_records 查
    if not p2_data and lot_no:
        try:
            lot_no_norm = normalize_lot_no(lot_no)
        except Exception:
            lot_no_norm = None

        if lot_no_norm is not None:
            p2_v2_stmt = select(P2Record).where(
                P2Record.tenant_id == current_tenant.id,
                P2Record.lot_no_norm == lot_no_norm,
            )
            if source_winder is not None:
                p2_v2_stmt = p2_v2_stmt.where(P2Record.winder_number == source_winder)
            else:
                p2_v2_stmt = p2_v2_stmt.order_by(P2Record.winder_number)

            p2_v2_result = await db.execute(p2_v2_stmt)
            p2_v2 = p2_v2_result.scalar_one_or_none()
            if not p2_v2 and source_winder is not None:
                # 如果指定 winder 找不到，退而求其次拿第一筆
                p2_any_stmt = select(P2Record).where(
                    P2Record.tenant_id == current_tenant.id,
                    P2Record.lot_no_norm == lot_no_norm,
                ).order_by(P2Record.winder_number)
                p2_any_result = await db.execute(p2_any_stmt)
                p2_v2 = p2_any_result.scalar_one_or_none()
                if p2_v2:
                    p2_data = _p2_record_to_dict(p2_v2)
                    p2_data['warning'] = 'Exact winder match not found (V2 fallback, using first)'
            elif p2_v2:
                p2_data = _p2_record_to_dict(p2_v2)

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

    # V2 fallback: 舊路徑 P1 找不到時，嘗試從 p1_records 查
    if not p1_data and lot_no:
        try:
            lot_no_norm = normalize_lot_no(lot_no)
        except Exception:
            lot_no_norm = None

        if lot_no_norm is not None:
            p1_v2_stmt = select(P1Record).where(
                P1Record.tenant_id == current_tenant.id,
                P1Record.lot_no_norm == lot_no_norm,
            )
            p1_v2_result = await db.execute(p1_v2_stmt)
            p1_v2 = p1_v2_result.scalar_one_or_none()
            if p1_v2:
                p1_data = _p1_record_to_dict(p1_v2)

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
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
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

    # V2 fallback for P2
    if not p2_data:
        try:
            lot_no_norm = normalize_lot_no(lot_no)
        except Exception:
            lot_no_norm = None

        if lot_no_norm is not None:
            p2_v2_stmt = select(P2Record).where(
                P2Record.tenant_id == current_tenant.id,
                P2Record.lot_no_norm == lot_no_norm,
                P2Record.winder_number == winder_number,
            )
            p2_v2_result = await db.execute(p2_v2_stmt)
            p2_v2 = p2_v2_result.scalar_one_or_none()
            if p2_v2:
                p2_data = _p2_record_to_dict(p2_v2)

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

    # V2 fallback for P1
    if not p1_data:
        try:
            lot_no_norm = normalize_lot_no(lot_no)
        except Exception:
            lot_no_norm = None

        if lot_no_norm is not None:
            p1_v2_stmt = select(P1Record).where(
                P1Record.tenant_id == current_tenant.id,
                P1Record.lot_no_norm == lot_no_norm,
            )
            p1_v2_result = await db.execute(p1_v2_stmt)
            p1_v2 = p1_v2_result.scalar_one_or_none()
            if p1_v2:
                p1_data = _p1_record_to_dict(p1_v2)

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

    base_lot, parsed_winder = _extract_base_lot_and_winder_from_p3_payload(row_data)

    return {
        "id": item.id,
        "record_id": item.record_id,
        "data_type": DataType.P3.value,
        "display_name": f"P3追蹤 ({item.lot_no})",
        # lot_no here should represent base lot for linkage (e.g. 2507173_02)
        "lot_no": base_lot or item.lot_no,
        "product_id": item.product_id,
        "machine_no": item.machine_no,
        "mold_no": item.mold_no,
        "production_lot": item.production_lot,
        "source_winder": item.source_winder if item.source_winder is not None else parsed_winder,
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


def _extras_to_additional_data(extras: Any) -> Dict[str, Any]:
    """Normalize V2 extras payload to additional_data shape expected by frontend."""
    if not extras:
        return {}
    if isinstance(extras, dict) and 'rows' in extras and isinstance(extras.get('rows'), list):
        return extras
    if isinstance(extras, dict):
        return {'rows': [extras]}
    return {'rows': [extras]}


def _p3_record_to_dict(rec: P3Record) -> Dict[str, Any]:
    return {
        "id": str(rec.id),
        "data_type": DataType.P3.value,
        "display_name": f"P3追蹤 ({rec.lot_no_raw})",
        "lot_no": rec.lot_no_raw,
        "product_id": rec.product_id,
        "machine_no": rec.machine_no,
        "mold_no": rec.mold_no,
        "production_date": str(rec.production_date_yyyymmdd) if rec.production_date_yyyymmdd else None,
        "additional_data": _extras_to_additional_data(rec.extras),
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


def _p2_record_to_dict(rec: P2Record) -> Dict[str, Any]:
    return {
        "id": str(rec.id),
        "data_type": DataType.P2.value,
        "display_name": f"P2 ({rec.lot_no_raw})",
        "lot_no": rec.lot_no_raw,
        "winder_number": rec.winder_number,
        "additional_data": _extras_to_additional_data(rec.extras),
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


def _p1_record_to_dict(rec: P1Record) -> Dict[str, Any]:
    return {
        "id": str(rec.id),
        "data_type": DataType.P1.value,
        "display_name": f"P1 ({rec.lot_no_raw})",
        "lot_no": rec.lot_no_raw,
        "additional_data": rec.extras,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


def _extract_source_winder_from_v2_extras(extras: Any) -> Optional[int]:
    """Try to extract source winder number from V2 extras/rows (best-effort)."""
    try:
        rows = None
        if isinstance(extras, dict) and isinstance(extras.get('rows'), list):
            rows = extras.get('rows')
        if rows and len(rows) > 0 and isinstance(rows[0], dict):
            payload = rows[0]
        elif isinstance(extras, dict):
            payload = extras
        else:
            return None

        p3_no = payload.get('P3_No.') or payload.get('P3 No.') or payload.get('p3_no') or payload.get('P3NO')
        if not p3_no:
            # 有些資料會把 lot no 放在 "lot no" / "Lot No"，也可當作候選
            p3_no = payload.get('lot no') or payload.get('Lot No')
        if not p3_no:
            return None

        parts = str(p3_no).strip().split('_')
        if len(parts) >= 3:
            winder_part = parts[-2]
            if winder_part.isdigit():
                return int(winder_part)
    except Exception:
        return None

    return None


def _get_first_row_payload(p3_data: Any) -> Dict[str, Any]:
    """Get first row dict from traceability p3 payload if present."""
    try:
        if not isinstance(p3_data, dict):
            return {}
        additional = p3_data.get('additional_data') or {}
        if isinstance(additional, dict) and isinstance(additional.get('rows'), list) and additional['rows']:
            first = additional['rows'][0]
            return first if isinstance(first, dict) else {}
    except Exception:
        return {}
    return {}


def _extract_base_lot_and_winder_from_p3_payload(payload: Any) -> tuple[Optional[str], Optional[int]]:
    """Best-effort parse base lot + winder from P3 row payload.

    Examples:
    - "lot no": "2507173_02_17" -> base="2507173_02", winder=17
    - "P3_No.": "2503273_03_14_301" -> base="2503273_03", winder=14
    """
    if not isinstance(payload, dict):
        return None, None

    raw = (
        payload.get('P3_No.')
        or payload.get('P3 No.')
        or payload.get('p3_no')
        or payload.get('P3NO')
        or payload.get('lot no')
        or payload.get('Lot No')
        or payload.get('lot_no')
    )
    if raw is None:
        return None, None

    s = str(raw).strip()
    if not s:
        return None, None

    parts = [p for p in s.split('_') if p]
    if not parts:
        return None, None

    # Handle trailing "copy" tokens
    if parts and 'copy' in parts[-1].lower():
        parts = parts[:-1]
    if len(parts) < 2:
        return None, None

    # Pattern A: baseLot_winder (e.g. 2507173_02_17)
    last = parts[-1]
    if last.isdigit() and 1 <= len(last) <= 2:
        return '_'.join(parts[:-1]), int(last)

    # Pattern B: baseLot_winder_batch (e.g. 2503273_03_14_301)
    second_last = parts[-2]
    if second_last.isdigit() and 1 <= len(second_last) <= 2:
        return '_'.join(parts[:-2]), int(second_last)

    return None, None

