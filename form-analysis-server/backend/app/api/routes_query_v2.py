from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_, func
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
            "machine_no": r.machine_no,
            "mold_no": r.mold_no,
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
