from typing import List, Optional, Dict, Any, Iterable
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_, func, cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.deps import get_db, get_current_tenant
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.utils.normalization import normalize_lot_no

router = APIRouter()

# --- Schemas ---

class AdvancedSearchRequest(BaseModel):
    lot_no: Optional[str] = None
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    machine_no: Optional[str] = None
    mold_no: Optional[str] = None
    winder_number: Optional[int] = None
    
    page: int = 1
    page_size: int = 20

class TraceResult(BaseModel):
    trace_key: str  # Usually lot_no_norm
    p1_found: bool
    p2_count: int
    p3_count: int
    
class AdvancedSearchResponse(BaseModel):
    total: int
    results: List[TraceResult]

class TraceDetailResponse(BaseModel):
    trace_key: str
    p1: Optional[Dict[str, Any]]
    p2: List[Dict[str, Any]]
    p3: List[Dict[str, Any]]


# --- Legacy-compatible schemas (for frontend QueryPage) ---

class QueryRecordV2Compat(BaseModel):
    id: str
    lot_no: str
    data_type: str  # 'P1' | 'P2' | 'P3'
    production_date: Optional[str] = None
    created_at: str
    display_name: str

    # Optional known fields used by frontend (kept for compatibility)
    winder_number: Optional[int] = None
    product_id: Optional[str] = None
    machine_no: Optional[str] = None
    mold_no: Optional[str] = None
    source_winder: Optional[int] = None
    specification: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None


class QueryResponseV2Compat(BaseModel):
    total_count: int
    page: int
    page_size: int
    records: List[QueryRecordV2Compat]


def _yyyymmdd_to_yyyy_mm_dd(v: Optional[int]) -> Optional[str]:
    if not v:
        return None
    s = str(v)
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def _first_row(extras: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(extras, dict):
        return None
    rows = extras.get('rows')
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    return first if isinstance(first, dict) else None


def _extract_spec_from_row(row: Optional[Dict[str, Any]]) -> Optional[str]:
    if not row:
        return None
    for key in [
        'specification', 'Specification', 'SPECIFICATION',
        '規格', '產品規格', 'P3規格',
        'Spec', 'spec',
    ]:
        v = row.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _extract_production_date_from_row(row: Optional[Dict[str, Any]]) -> Optional[str]:
    if not row:
        return None
    for key in [
        'production_date', 'Production Date', 'Production date',
        '生產日期', '日期',
    ]:
        v = row.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        # allow YYYY-MM-DD, YYYY/MM/DD, YYMMDD etc (frontend will format too)
        return s
    return None


def _derive_machine_mold(record_machine: Optional[str], record_mold: Optional[str], extras: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    machine = None
    mold = None
    if record_machine and str(record_machine).strip() and str(record_machine).upper() != 'UNKNOWN':
        machine = str(record_machine).strip()
    if record_mold and str(record_mold).strip() and str(record_mold).upper() != 'UNKNOWN':
        mold = str(record_mold).strip()
    if machine and mold:
        return machine, mold

    m2, m3 = _derive_machine_mold_from_extras(extras)
    return machine or m2, mold or m3


def _p1_to_query_record(r: P1Record) -> QueryRecordV2Compat:
    row0 = _first_row(r.extras)
    display = r.lot_no_raw
    return QueryRecordV2Compat(
        id=str(r.id),
        lot_no=r.lot_no_raw,
        data_type='P1',
        production_date=_extract_production_date_from_row(row0),
        created_at=r.created_at.isoformat(),
        display_name=display,
        additional_data=(r.extras if isinstance(r.extras, dict) else {}),  # 修復: 返回完整 extras 而非只有 row0
    )


def _p2_to_query_record_with_items(p2_record: P2Record, items: list) -> QueryRecordV2Compat:
    """
    組合 P2Record + P2ItemsV2 為查詢結果
    items: List[P2ItemV2]
    """
    # 將 items 轉為 rows 格式（前端期望）
    rows = []
    for item in items:
        row = item.row_data if isinstance(item.row_data, dict) else {}
        row['winder_number'] = item.winder_number
        # 加入結構化欄位
        for field in ['sheet_width', 'thickness1', 'thickness2', 'thickness3',
                     'thickness4', 'thickness5', 'thickness6', 'thickness7',
                     'appearance', 'rough_edge', 'slitting_result']:
            val = getattr(item, field, None)
            if val is not None:
                row[field] = val
        rows.append(row)
    
    # 按 winder_number 排序
    rows.sort(key=lambda x: x.get('winder_number', 0))
    
    # 從第一個 item 提取生產日期
    first_item = items[0] if items else None
    production_date = None
    if first_item and isinstance(first_item.row_data, dict):
        for key in ['Production Date', 'production_date', '生產日期', 'date']:
            if key in first_item.row_data:
                production_date = first_item.row_data[key]
                break
    
    return QueryRecordV2Compat(
        id=str(p2_record.id),
        lot_no=p2_record.lot_no_raw,
        data_type='P2',
        production_date=production_date,
        created_at=p2_record.created_at.isoformat(),
        display_name=p2_record.lot_no_raw,
        winder_number=None,  # 合併模式
        additional_data={'rows': rows},
    )


def _p2_to_query_record(r: P2Record) -> QueryRecordV2Compat:
    """Legacy fallback - 當沒有 items 時使用"""
    display = f"{r.lot_no_raw} (W{r.winder_number})"
    row0 = _first_row(r.extras)
    return QueryRecordV2Compat(
        id=str(r.id),
        lot_no=r.lot_no_raw,
        data_type='P2',
        production_date=_extract_production_date_from_row(row0),
        created_at=r.created_at.isoformat(),
        display_name=display,
        winder_number=r.winder_number,
        additional_data=(r.extras if isinstance(r.extras, dict) else None),
    )


def _merge_p2_records(records: list[P2Record]) -> list[QueryRecordV2Compat]:
    """將相同 lot_no 的 P2 Records (20個winders) 合併成單一筆查詢記錄
    
    前端期望的資料結構是 additional_data.rows 陣列，每個 row 是扁平的 dict。
    """
    from collections import defaultdict
    
    # 按 lot_no_norm 分組
    grouped = defaultdict(list)
    for r in records:
        grouped[r.lot_no_norm].append(r)
    
    merged_results = []
    for lot_no_norm, lot_records in grouped.items():
        # 排序確保 winder 順序一致
        lot_records.sort(key=lambda x: x.winder_number)
        
        # 使用第一個 record 的基本資訊
        first = lot_records[0]
        row0 = _first_row(first.extras)
        
        # 將所有 winder 的 extras 展開為 rows 陣列（前端期望的格式）
        rows = []
        for rec in lot_records:
            # P2Record.extras 是扁平的 dict，包含所有欄位
            # 直接使用 extras 作為 row，這樣前端可以正確渲染表格
            if isinstance(rec.extras, dict):
                row = rec.extras.copy()
                # 確保 winder_number 包含在 row 中（前端可能需要）
                row['winder_number'] = rec.winder_number
                rows.append(row)
        
        # 組裝 additional_data (包含 rows 陣列)
        merged_extras = {
            'lot_no': first.lot_no_raw,
            'rows': rows  # 前端期望此欄位名稱
        }
        
        # 從第一個 winder 的 extras 提取共同資訊（保留共同欄位）
        if isinstance(first.extras, dict):
            for key in ['format', 'Format', '規格', 'production_date', 'Production Date', '生產日期']:
                if key in first.extras:
                    merged_extras[key] = first.extras[key]
        
        merged_results.append(QueryRecordV2Compat(
            id=str(first.id),  # 使用第一個 winder 的 ID
            lot_no=first.lot_no_raw,
            data_type='P2',
            production_date=_extract_production_date_from_row(row0),
            created_at=first.created_at.isoformat(),
            display_name=first.lot_no_raw,  # 不再顯示 winder number
            winder_number=None,  # 合併後不顯示單一 winder
            additional_data=merged_extras,
        ))
    
    return merged_results


def _p3_to_query_record_with_items(p3_record: P3Record, items: list) -> QueryRecordV2Compat:
    """
    組合 P3Record + P3ItemsV2 為查詢結果
    items: List[P3ItemV2]
    """
    # 將 items 轉為 rows 格式
    rows = []
    for item in items:
        row = item.row_data if isinstance(item.row_data, dict) else {}
        row['row_no'] = item.row_no
        row['product_id'] = item.product_id
        row['source_winder'] = item.source_winder
        row['specification'] = item.specification
        rows.append(row)
    
    # 按 row_no 排序
    rows.sort(key=lambda x: x.get('row_no', 0))
    
    return QueryRecordV2Compat(
        id=str(p3_record.id),
        lot_no=p3_record.lot_no_raw,
        data_type='P3',
        production_date=_yyyymmdd_to_yyyy_mm_dd(p3_record.production_date_yyyymmdd),
        created_at=p3_record.created_at.isoformat(),
        display_name=p3_record.product_id or p3_record.lot_no_raw,
        product_id=p3_record.product_id,
        machine_no=p3_record.machine_no,
        mold_no=p3_record.mold_no,
        specification=items[0].specification if items else None,
        additional_data={'rows': rows},
    )


def _p3_to_query_record(r: P3Record) -> QueryRecordV2Compat:
    """Legacy fallback - 當沒有 items 時使用"""
    machine, mold = _derive_machine_mold(r.machine_no, r.mold_no, r.extras)
    display = r.product_id or r.lot_no_raw
    row0 = _first_row(r.extras)
    return QueryRecordV2Compat(
        id=str(r.id),
        lot_no=r.lot_no_raw,
        data_type='P3',
        production_date=_yyyymmdd_to_yyyy_mm_dd(r.production_date_yyyymmdd),
        created_at=r.created_at.isoformat(),
        display_name=display,
        product_id=r.product_id,
        machine_no=machine,
        mold_no=mold,
        specification=_extract_spec_from_row(row0),
        additional_data=(r.extras if isinstance(r.extras, dict) else None),
    )


def _derive_machine_mold_from_extras(extras: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    try:
        rows = extras.get("rows") if isinstance(extras, dict) else None
        if not rows or not isinstance(rows, list):
            return None, None
        first = rows[0] if rows else None
        if not isinstance(first, dict):
            return None, None
        machine = (
            first.get("Machine NO")
            or first.get("Machine No")
            or first.get("machine_no")
            or first.get("Machine")
            or first.get("machine")
        )
        mold = (
            first.get("Mold NO")
            or first.get("Mold No")
            or first.get("mold_no")
            or first.get("Mold")
            or first.get("mold")
        )
        machine_s = str(machine).strip() if machine else None
        mold_s = str(mold).strip() if mold else None
        return machine_s, mold_s
    except Exception:
        return None, None

# --- Routes ---

@router.post("/advanced", response_model=AdvancedSearchResponse)
async def advanced_search(
    criteria: AdvancedSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Advanced search for traceability.
    Returns a list of trace keys (lot_no_norm) that match the criteria.
    """
    # Strategy:
    # 1. Determine which tables to query based on criteria
    # 2. Find matching lot_no_norm from those tables
    # 3. Intersect the sets of lot_no_norm
    # 4. For the resulting lots, count P1/P2/P3 records
    
    candidate_lots = None
    
    # 1. Filter by Lot No (P1/P2/P3)
    if criteria.lot_no:
        try:
            norm_lot = normalize_lot_no(criteria.lot_no)
            candidate_lots = {norm_lot}
        except Exception:
            # If normalization fails, return empty results immediately
            return AdvancedSearchResponse(total=0, results=[])
        
    # 2. Filter by Date/Machine/Mold (P3)
    if criteria.date_start or criteria.date_end or criteria.machine_no or criteria.mold_no:
        stmt = select(P3Record.lot_no_norm).where(P3Record.tenant_id == current_tenant.id)
        
        if criteria.date_start:
            start_int = int(criteria.date_start.strftime("%Y%m%d"))
            stmt = stmt.where(P3Record.production_date_yyyymmdd >= start_int)
        if criteria.date_end:
            end_int = int(criteria.date_end.strftime("%Y%m%d"))
            stmt = stmt.where(P3Record.production_date_yyyymmdd <= end_int)
        if criteria.machine_no:
            stmt = stmt.where(P3Record.machine_no == criteria.machine_no)
        if criteria.mold_no:
            stmt = stmt.where(P3Record.mold_no == criteria.mold_no)
            
        result = await db.execute(stmt)
        p3_lots = set(result.scalars().all())
        
        if candidate_lots is None:
            candidate_lots = p3_lots
        else:
            candidate_lots &= p3_lots
            
    # 3. Filter by Winder (P2)
    if criteria.winder_number is not None:
        stmt = select(P2Record.lot_no_norm).where(
            P2Record.tenant_id == current_tenant.id,
            P2Record.winder_number == criteria.winder_number
        )
        result = await db.execute(stmt)
        p2_lots = set(result.scalars().all())
        
        if candidate_lots is None:
            candidate_lots = p2_lots
        else:
            candidate_lots &= p2_lots
            
    # If no criteria provided, return empty or recent (limit to avoid full scan)
    if candidate_lots is None:
        # Default: fetch recent P1 lots
        stmt = select(P1Record.lot_no_norm).where(P1Record.tenant_id == current_tenant.id).limit(100)
        result = await db.execute(stmt)
        candidate_lots = set(result.scalars().all())

    # Pagination
    sorted_lots = sorted(list(candidate_lots))
    total = len(sorted_lots)
    start = (criteria.page - 1) * criteria.page_size
    end = start + criteria.page_size
    page_lots = sorted_lots[start:end]
    
    results = []
    for lot in page_lots:
        # Count P1
        p1_stmt = select(func.count()).select_from(P1Record).where(
            P1Record.tenant_id == current_tenant.id,
            P1Record.lot_no_norm == lot
        )
        p1_count = (await db.execute(p1_stmt)).scalar()
        
        # Count P2
        p2_stmt = select(func.count()).select_from(P2Record).where(
            P2Record.tenant_id == current_tenant.id,
            P2Record.lot_no_norm == lot
        )
        p2_count = (await db.execute(p2_stmt)).scalar()
        
        # Count P3
        p3_stmt = select(func.count()).select_from(P3Record).where(
            P3Record.tenant_id == current_tenant.id,
            P3Record.lot_no_norm == lot
        )
        p3_count = (await db.execute(p3_stmt)).scalar()
        
        results.append(TraceResult(
            trace_key=str(lot),
            p1_found=p1_count > 0,
            p2_count=p2_count,
            p3_count=p3_count
        ))
        
    return AdvancedSearchResponse(total=total, results=results)


@router.get("/lots/suggestions", response_model=List[str])
async def suggest_lots(
    term: str = Query("", description="lot no prefix/substring"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    t = (term or '').strip()
    if not t:
        return []

    # Search raw lot strings across P1/P2/P3
    like = f"%{t}%"
    p1_stmt = select(P1Record.lot_no_raw).where(
        P1Record.tenant_id == current_tenant.id,
        P1Record.lot_no_raw.ilike(like),
    ).limit(limit)
    p2_stmt = select(P2Record.lot_no_raw).where(
        P2Record.tenant_id == current_tenant.id,
        P2Record.lot_no_raw.ilike(like),
    ).limit(limit)
    p3_stmt = select(P3Record.lot_no_raw).where(
        P3Record.tenant_id == current_tenant.id,
        P3Record.lot_no_raw.ilike(like),
    ).limit(limit)

    lots: List[str] = []
    seen = set()
    for stmt in [p1_stmt, p2_stmt, p3_stmt]:
        result = await db.execute(stmt)
        for (lot,) in result.fetchall():
            if not lot:
                continue
            s = str(lot)
            if s not in seen:
                seen.add(s)
                lots.append(s)
            if len(lots) >= limit:
                return lots
    return lots


@router.get("/options/{field_name}", response_model=List[str])
async def get_field_options_v2(
    field_name: str,
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    field = field_name.strip().lower()
    if field not in {"machine_no", "mold_no", "specification", "winder_number"}:
        raise HTTPException(status_code=400, detail=f"Unsupported field: {field_name}")

    if field == "machine_no":
        stmt = (
            select(P3Record.machine_no)
            .where(P3Record.tenant_id == current_tenant.id)
            .where(P3Record.machine_no.isnot(None))
            .distinct()
            .order_by(P3Record.machine_no)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [str(v[0]).strip() for v in result.fetchall() if v[0] and str(v[0]).strip()]

    if field == "mold_no":
        stmt = (
            select(P3Record.mold_no)
            .where(P3Record.tenant_id == current_tenant.id)
            .where(P3Record.mold_no.isnot(None))
            .distinct()
            .order_by(P3Record.mold_no)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [str(v[0]).strip() for v in result.fetchall() if v[0] and str(v[0]).strip()]

    # specification: 統一規格選項，從 P1/P2/P3 的 extras 中提取
    if field == "specification":
        specs: List[str] = []
        seen = set()
        
        # P1: extras.Specification
        p1_stmt = (
            select(P1Record.extras)
            .where(P1Record.tenant_id == current_tenant.id)
            .limit(limit)
        )
        p1_result = await db.execute(p1_stmt)
        for (extras,) in p1_result.fetchall():
            if isinstance(extras, dict):
                spec = extras.get('Specification') or extras.get('specification') or extras.get('規格')
                if spec and str(spec).strip() and str(spec).strip() not in seen:
                    seen.add(str(spec).strip())
                    specs.append(str(spec).strip())
        
        # P2: extras.format
        p2_stmt = (
            select(P2Record.extras)
            .where(P2Record.tenant_id == current_tenant.id)
            .limit(limit)
        )
        p2_result = await db.execute(p2_stmt)
        for (extras,) in p2_result.fetchall():
            if isinstance(extras, dict):
                spec = extras.get('format') or extras.get('Format') or extras.get('規格')
                if spec and str(spec).strip() and str(spec).strip() not in seen:
                    seen.add(str(spec).strip())
                    specs.append(str(spec).strip())
        
        # P3: extras.rows[0].Specification
        p3_stmt = (
            select(P3Record.extras)
            .where(P3Record.tenant_id == current_tenant.id)
            .limit(limit)
        )
        p3_result = await db.execute(p3_stmt)
        for (extras,) in p3_result.fetchall():
            row0 = _first_row(extras)
            spec = _extract_spec_from_row(row0)
            if spec and spec not in seen:
                seen.add(spec)
                specs.append(spec)
        
        specs.sort()
        return specs[:limit]
    
    # winder_number: 從 P2/P3 的 extras 中提取
    if field == "winder_number":
        winders: List[str] = []
        seen = set()
        
        # P2: extras.rows[].winder_number
        p2_stmt = (
            select(P2Record.extras)
            .where(P2Record.tenant_id == current_tenant.id)
            .limit(limit)
        )
        p2_result = await db.execute(p2_stmt)
        for (extras,) in p2_result.fetchall():
            if isinstance(extras, dict) and 'rows' in extras:
                rows = extras.get('rows', [])
                if isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, dict):
                            winder = row.get('winder_number') or row.get('Winder Number') or row.get('winder')
                            if winder and str(winder).strip() and str(winder).strip() not in seen:
                                seen.add(str(winder).strip())
                                winders.append(str(winder).strip())
        
        # P3: extras.rows[0].source_winder (如果有的話)
        p3_stmt = (
            select(P3Record.extras)
            .where(P3Record.tenant_id == current_tenant.id)
            .limit(limit)
        )
        p3_result = await db.execute(p3_stmt)
        for (extras,) in p3_result.fetchall():
            row0 = _first_row(extras)
            if row0:
                winder = row0.get('source_winder') or row0.get('Source Winder') or row0.get('winder')
                if winder and str(winder).strip() and str(winder).strip() not in seen:
                    seen.add(str(winder).strip())
                    winders.append(str(winder).strip())
        
        winders.sort(key=lambda x: (x.isdigit() and int(x) or 999999, x))
        return winders[:limit]
    
    return []


@router.get("/records", response_model=QueryResponseV2Compat)
async def query_records_v2(
    lot_no: Optional[str] = Query(None),
    data_type: Optional[str] = Query(None, description="P1|P2|P3"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    # Delegate to advanced with simple params
    return await query_records_advanced_v2(
        lot_no=lot_no,
        production_date_from=None,
        production_date_to=None,
        machine_no=None,
        mold_no=None,
        product_id=None,
        specification=None,
        winder_number=None,
        data_type=data_type,
        page=page,
        page_size=page_size,
        db=db,
        current_tenant=current_tenant,
    )


@router.get("/records/advanced", response_model=QueryResponseV2Compat)
async def query_records_advanced_v2(
    lot_no: Optional[str] = Query(None),
    production_date_from: Optional[str] = Query(None),
    production_date_to: Optional[str] = Query(None),
    machine_no: Optional[str] = Query(None),
    mold_no: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    specification: Optional[str] = Query(None, description="統一規格搜尋 (P1.Specification, P2.format, P3.Specification)"),
    winder_number: Optional[str] = Query(None, description="Winder Number (P2/P3)"),
    data_type: Optional[str] = Query(None, description="P1|P2|P3"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    dt = (data_type or '').strip().upper() or None
    allow = {"P1", "P2", "P3"}
    if dt and dt not in allow:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    lot_no_raw = (lot_no or '').strip() or None
    lot_no_norm: Optional[int]
    try:
        lot_no_norm = normalize_lot_no(lot_no_raw) if lot_no_raw else None
    except Exception:
        lot_no_norm = None

    # Parse date range for P3 (YYYY-MM-DD)
    def to_int_yyyymmdd(s: Optional[str]) -> Optional[int]:
        if not s:
            return None
        try:
            return int(date.fromisoformat(s).strftime('%Y%m%d'))
        except Exception:
            return None

    date_from_i = to_int_yyyymmdd(production_date_from)
    date_to_i = to_int_yyyymmdd(production_date_to)

    records: List[QueryRecordV2Compat] = []

    # P1
    if dt in (None, "P1"):
        p1_stmt = select(P1Record).where(P1Record.tenant_id == current_tenant.id)
        if lot_no_norm is not None:
            p1_stmt = p1_stmt.where(P1Record.lot_no_norm == lot_no_norm)
        elif lot_no_raw:
            p1_stmt = p1_stmt.where(P1Record.lot_no_raw.ilike(f"%{lot_no_raw}%"))
        
        # 統一規格搜尋: P1 查 extras.Specification
        if specification and specification.strip():
            spec = specification.strip()
            p1_stmt = p1_stmt.where(
                or_(
                    func.jsonb_extract_path_text(cast(P1Record.extras, JSONB), 'Specification').ilike(f"%{spec}%"),
                    func.jsonb_extract_path_text(cast(P1Record.extras, JSONB), 'specification').ilike(f"%{spec}%"),
                    func.jsonb_extract_path_text(cast(P1Record.extras, JSONB), '規格').ilike(f"%{spec}%"),
                )
            )
        
        p1_stmt = p1_stmt.order_by(P1Record.created_at.desc()).limit(page * page_size)
        p1_result = await db.execute(p1_stmt)
        records.extend([_p1_to_query_record(r) for r in p1_result.scalars().all()])

    # P2
    if dt in (None, "P2"):
        from app.models.p2_item_v2 import P2ItemV2
        from sqlalchemy.orm import selectinload
        
        # 查詢 P2Record，預先加載 items_v2
        p2_stmt = select(P2Record).options(selectinload(P2Record.items_v2)).where(
            P2Record.tenant_id == current_tenant.id
        )
        if lot_no_norm is not None:
            p2_stmt = p2_stmt.where(P2Record.lot_no_norm == lot_no_norm)
        elif lot_no_raw:
            p2_stmt = p2_stmt.where(P2Record.lot_no_raw.ilike(f"%{lot_no_raw}%"))
        
        # Winder Number 篩選（在 items 層級）
        winder_filter_applied = False
        winder_val = None
        if winder_number and winder_number.strip():
            try:
                winder_val = int(winder_number.strip())
                winder_filter_applied = True
            except ValueError:
                pass
        
        # 統一規格搜尋: 在 items 的 row_data 中搜尋
        if specification and specification.strip():
            spec = specification.strip()
            # 需要 JOIN p2_items_v2 來篩選
            p2_stmt = p2_stmt.join(P2ItemV2, P2Record.id == P2ItemV2.p2_record_id)
            p2_stmt = p2_stmt.where(
                or_(
                    func.jsonb_extract_path_text(cast(P2ItemV2.row_data, JSONB), 'format').ilike(f"%{spec}%"),
                    func.jsonb_extract_path_text(cast(P2ItemV2.row_data, JSONB), 'Format').ilike(f"%{spec}%"),
                    func.jsonb_extract_path_text(cast(P2ItemV2.row_data, JSONB), '規格').ilike(f"%{spec}%"),
                )
            ).distinct()
        
        p2_stmt = p2_stmt.order_by(P2Record.created_at.desc())
        p2_result = await db.execute(p2_stmt)
        p2_records = p2_result.scalars().unique().all()

        legacy_records: list[P2Record] = []

        # 處理每個 P2Record + 其 items_v2；若沒有 items_v2，走 legacy merge/fallback
        for p2_record in p2_records:
            items = list(p2_record.items_v2 or [])

            # 套用 winder 篩選（items 層級）
            if winder_filter_applied and winder_val is not None:
                items = [item for item in items if item.winder_number == winder_val]

            if items:
                records.append(_p2_to_query_record_with_items(p2_record, items))
            else:
                # Legacy: 沒有 items_v2 的 P2Record 可能仍以 extras 方式保存
                if winder_filter_applied and winder_val is not None:
                    if p2_record.winder_number != winder_val:
                        continue
                legacy_records.append(p2_record)

        if legacy_records:
            records.extend(_merge_p2_records(legacy_records))

    # P3
    if dt in (None, "P3"):
        from app.models.p3_item_v2 import P3ItemV2
        from sqlalchemy.orm import selectinload
        
        # 查詢 P3Record，預先加載 items_v2
        p3_stmt = select(P3Record).options(selectinload(P3Record.items_v2)).where(
            P3Record.tenant_id == current_tenant.id
        )
        if lot_no_norm is not None:
            p3_stmt = p3_stmt.where(P3Record.lot_no_norm == lot_no_norm)
        elif lot_no_raw:
            p3_stmt = p3_stmt.where(P3Record.lot_no_raw.ilike(f"%{lot_no_raw}%"))
        if date_from_i is not None:
            p3_stmt = p3_stmt.where(P3Record.production_date_yyyymmdd >= date_from_i)
        if date_to_i is not None:
            p3_stmt = p3_stmt.where(P3Record.production_date_yyyymmdd <= date_to_i)
        if machine_no and machine_no.strip():
            p3_stmt = p3_stmt.where(P3Record.machine_no == machine_no.strip())
        if mold_no and mold_no.strip():
            p3_stmt = p3_stmt.where(P3Record.mold_no == mold_no.strip())
        if product_id and product_id.strip():
            p3_stmt = p3_stmt.where(P3Record.product_id.ilike(f"%{product_id.strip()}%"))

        # 統一規格搜尋: 在 items 的 specification 欄位中搜尋
        if specification and specification.strip():
            spec = specification.strip()
            p3_stmt = p3_stmt.join(P3ItemV2, P3Record.id == P3ItemV2.p3_record_id)
            p3_stmt = p3_stmt.where(P3ItemV2.specification.ilike(f"%{spec}%")).distinct()
        
        # Winder Number 篩選: 搜尋 items 的 source_winder
        if winder_number and winder_number.strip():
            try:
                winder_val = int(winder_number.strip())
                if not specification:  # 避免重複 JOIN
                    p3_stmt = p3_stmt.join(P3ItemV2, P3Record.id == P3ItemV2.p3_record_id)
                p3_stmt = p3_stmt.where(P3ItemV2.source_winder == winder_val).distinct()
            except ValueError:
                pass

        p3_stmt = p3_stmt.order_by(P3Record.created_at.desc())
        p3_result = await db.execute(p3_stmt)
        p3_records = p3_result.scalars().unique().all()
        
        # 處理每個 P3Record + 其 items
        for p3_record in p3_records:
            items = p3_record.items_v2
            if items:  # 只有有 items 的才顯示
                records.append(_p3_to_query_record_with_items(p3_record, items))

    # Sort and paginate in memory (simple, OK for current UI)
    records.sort(key=lambda r: r.created_at, reverse=True)
    total_count = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    page_records = records[start:end]

    return QueryResponseV2Compat(
        total_count=total_count,
        page=page,
        page_size=page_size,
        records=page_records,
    )

@router.get("/trace/{trace_key}", response_model=TraceDetailResponse)
async def get_trace_detail(
    trace_key: str,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Get full trace details for a given trace key (lot_no_norm).
    """
    try:
        lot_no_norm = int(trace_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid trace key format")
        
    # Fetch P1
    p1_stmt = select(P1Record).where(
        P1Record.tenant_id == current_tenant.id,
        P1Record.lot_no_norm == lot_no_norm
    )
    p1_result = await db.execute(p1_stmt)
    p1_record = p1_result.scalar_one_or_none()
    
    p1_data = None
    if p1_record:
        p1_data = {
            "id": p1_record.id,
            "lot_no_raw": p1_record.lot_no_raw,
            "extras": p1_record.extras,
            "created_at": p1_record.created_at
        }
        
    # Fetch P2
    p2_stmt = select(P2Record).where(
        P2Record.tenant_id == current_tenant.id,
        P2Record.lot_no_norm == lot_no_norm
    ).order_by(P2Record.winder_number)
    p2_result = await db.execute(p2_stmt)
    p2_records = p2_result.scalars().all()
    
    p2_data = [
        {
            "id": r.id,
            "winder_number": r.winder_number,
            "extras": r.extras,
            "created_at": r.created_at
        }
        for r in p2_records
    ]
    
    # Fetch P3
    p3_stmt = select(P3Record).where(
        P3Record.tenant_id == current_tenant.id,
        P3Record.lot_no_norm == lot_no_norm
    ).order_by(P3Record.production_date_yyyymmdd, P3Record.machine_no)
    p3_result = await db.execute(p3_stmt)
    p3_records = p3_result.scalars().all()
    
    p3_data = [
        {
            "id": r.id,
            "production_date": r.production_date_yyyymmdd,
            "machine_no": (
                _derive_machine_mold_from_extras(r.extras)[0]
                if str(r.machine_no).upper() == "UNKNOWN"
                else r.machine_no
            ),
            "mold_no": (
                _derive_machine_mold_from_extras(r.extras)[1]
                if str(r.mold_no).upper() == "UNKNOWN"
                else r.mold_no
            ),
            "extras": r.extras,
            "created_at": r.created_at
        }
        for r in p3_records
    ]
    
    return TraceDetailResponse(
        trace_key=trace_key,
        p1=p1_data,
        p2=p2_data,
        p3=p3_data
    )
