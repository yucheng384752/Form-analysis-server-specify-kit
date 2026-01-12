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
        additional_data=(row0 or {}),
    )


def _p2_to_query_record(r: P2Record) -> QueryRecordV2Compat:
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


def _p3_to_query_record(r: P3Record) -> QueryRecordV2Compat:
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
        p3_specification=None,
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
        p2_stmt = select(P2Record).where(P2Record.tenant_id == current_tenant.id)
        if lot_no_norm is not None:
            p2_stmt = p2_stmt.where(P2Record.lot_no_norm == lot_no_norm)
        elif lot_no_raw:
            p2_stmt = p2_stmt.where(P2Record.lot_no_raw.ilike(f"%{lot_no_raw}%"))
        
        # 統一規格搜尋: P2 查 extras.format
        if specification and specification.strip():
            spec = specification.strip()
            p2_stmt = p2_stmt.where(
                or_(
                    func.jsonb_extract_path_text(cast(P2Record.extras, JSONB), 'format').ilike(f"%{spec}%"),
                    func.jsonb_extract_path_text(cast(P2Record.extras, JSONB), 'Format').ilike(f"%{spec}%"),
                    func.jsonb_extract_path_text(cast(P2Record.extras, JSONB), '規格').ilike(f"%{spec}%"),
                )
            )
        
        # Winder Number 篩選: P2 查 extras.rows 中的 winder_number
        if winder_number and winder_number.strip():
            winder_val = winder_number.strip()
            # 在 P2Record 中，extras.rows 是陣列，每個 row 有 winder_number
            p2_stmt = p2_stmt.where(
                func.jsonb_path_exists(
                    cast(P2Record.extras, JSONB),
                    f'$.rows[*] ? (@.winder_number == "{winder_val}" || @."Winder Number" == "{winder_val}")'
                )
            )
        
        p2_stmt = p2_stmt.order_by(P2Record.created_at.desc()).limit(page * page_size)
        p2_result = await db.execute(p2_stmt)
        records.extend([_p2_to_query_record(r) for r in p2_result.scalars().all()])

    # P3
    if dt in (None, "P3"):
        p3_stmt = select(P3Record).where(P3Record.tenant_id == current_tenant.id)
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

        # 統一規格搜尋: P3 查 extras.rows[0].Specification
        if specification and specification.strip():
            spec = specification.strip()
            p3_stmt = p3_stmt.where(
                or_(
                    func.jsonb_extract_path_text(cast(P3Record.extras, JSONB), 'rows', '0', 'Specification').ilike(f"%{spec}%"),
                    func.jsonb_extract_path_text(cast(P3Record.extras, JSONB), 'rows', '0', 'specification').ilike(f"%{spec}%"),
                    func.jsonb_extract_path_text(cast(P3Record.extras, JSONB), 'rows', '0', '規格').ilike(f"%{spec}%"),
                )
            )
        
        # Winder Number 篩選: P3 查 source_winder (在 p3_items 表中)
        # 注意：p3_records 沒有直接的 winder 欄位，可能需要從 extras 提取
        if winder_number and winder_number.strip():
            winder_val = winder_number.strip()
            # 嘗試從 extras.rows[0] 中查找 source_winder 或類似欄位
            p3_stmt = p3_stmt.where(
                or_(
                    func.jsonb_extract_path_text(cast(P3Record.extras, JSONB), 'rows', '0', 'source_winder').ilike(f"%{winder_val}%"),
                    func.jsonb_extract_path_text(cast(P3Record.extras, JSONB), 'rows', '0', 'Source Winder').ilike(f"%{winder_val}%"),
                    func.jsonb_extract_path_text(cast(P3Record.extras, JSONB), 'rows', '0', 'winder').ilike(f"%{winder_val}%"),
                )
            )

        p3_stmt = p3_stmt.order_by(P3Record.created_at.desc()).limit(page * page_size)
        p3_result = await db.execute(p3_stmt)
        records.extend([_p3_to_query_record(r) for r in p3_result.scalars().all()])

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
