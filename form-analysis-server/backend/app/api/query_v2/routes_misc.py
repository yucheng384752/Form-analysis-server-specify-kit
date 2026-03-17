from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_db
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record

from .helpers import (
    _derive_machine_mold_from_extras,
    _p1_to_query_record,
    _p2_to_query_record,
    _p2_to_query_record_with_items,
    _p3_to_query_record,
    _p3_to_query_record_with_items,
    _yyyymmdd_to_yyyy_mm_dd,
)
from .schemas import (
    QueryRecordV2Compat,
    RecordStatsV2Compat,
    TraceDetailResponse,
)

router = APIRouter()


@router.get("/records/stats", response_model=RecordStatsV2Compat)
async def get_record_stats_v2(
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> RecordStatsV2Compat:
    """Tenant-scoped record stats across v2 P1/P2/P3 tables."""
    p1_count = await db.scalar(
        select(func.count())
        .select_from(P1Record)
        .where(P1Record.tenant_id == current_tenant.id)
    )
    p2_count = await db.scalar(
        select(func.count())
        .select_from(P2Record)
        .where(P2Record.tenant_id == current_tenant.id)
    )
    p3_count = await db.scalar(
        select(func.count())
        .select_from(P3Record)
        .where(P3Record.tenant_id == current_tenant.id)
    )

    p1_records = int(p1_count or 0)
    p2_records = int(p2_count or 0)
    p3_records = int(p3_count or 0)
    total_records = p1_records + p2_records + p3_records

    if total_records == 0:
        return RecordStatsV2Compat(
            total_records=0,
            unique_lots=0,
            p1_records=0,
            p2_records=0,
            p3_records=0,
            latest_production_date=None,
            earliest_production_date=None,
        )

    lot_union = union_all(
        select(P1Record.lot_no_norm.label("lot_no_norm")).where(
            P1Record.tenant_id == current_tenant.id
        ),
        select(P2Record.lot_no_norm.label("lot_no_norm")).where(
            P2Record.tenant_id == current_tenant.id
        ),
        select(P3Record.lot_no_norm.label("lot_no_norm")).where(
            P3Record.tenant_id == current_tenant.id
        ),
    ).subquery()

    unique_lots = await db.scalar(
        select(func.count(func.distinct(lot_union.c.lot_no_norm)))
    )
    unique_lots = int(unique_lots or 0)

    date_row = (
        await db.execute(
            select(
                func.max(P3Record.production_date_yyyymmdd),
                func.min(P3Record.production_date_yyyymmdd),
            ).where(P3Record.tenant_id == current_tenant.id)
        )
    ).first()
    latest_yyyymmdd = date_row[0] if date_row else None
    earliest_yyyymmdd = date_row[1] if date_row else None

    return RecordStatsV2Compat(
        total_records=total_records,
        unique_lots=unique_lots,
        p1_records=p1_records,
        p2_records=p2_records,
        p3_records=p3_records,
        latest_production_date=_yyyymmdd_to_yyyy_mm_dd(latest_yyyymmdd),
        earliest_production_date=_yyyymmdd_to_yyyy_mm_dd(earliest_yyyymmdd),
    )


# NOTE: This must be declared after `/records/advanced`.
# Otherwise FastAPI can match `/records/{record_id}` first and reject
# `/records/advanced` with a 422 UUID parsing error.
@router.get("/records/{record_id}", response_model=QueryRecordV2Compat)
async def get_record_v2(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> QueryRecordV2Compat:
    """Lookup a single record by id across P1/P2/P3 tables (used by legacy fallback)."""
    # P1
    p1 = (
        await db.execute(
            select(P1Record).where(
                P1Record.tenant_id == current_tenant.id,
                P1Record.id == record_id,
            )
        )
    ).scalar_one_or_none()
    if p1:
        return _p1_to_query_record(p1)

    from sqlalchemy.orm import selectinload

    # P2
    p2 = (
        await db.execute(
            select(P2Record)
            .options(selectinload(P2Record.items_v2))
            .where(
                P2Record.tenant_id == current_tenant.id,
                P2Record.id == record_id,
            )
        )
    ).scalar_one_or_none()
    if p2:
        items = list(p2.items_v2 or [])
        return (
            _p2_to_query_record_with_items(p2, items)
            if items
            else _p2_to_query_record(p2)
        )

    # P3
    p3 = (
        await db.execute(
            select(P3Record)
            .options(selectinload(P3Record.items_v2))
            .where(
                P3Record.tenant_id == current_tenant.id,
                P3Record.id == record_id,
            )
        )
    ).scalar_one_or_none()
    if p3:
        items = list(p3.items_v2 or [])
        return (
            _p3_to_query_record_with_items(p3, items)
            if items
            else _p3_to_query_record(p3)
        )

    raise HTTPException(status_code=404, detail="Record not found")


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
        P1Record.tenant_id == current_tenant.id, P1Record.lot_no_norm == lot_no_norm
    )
    p1_result = await db.execute(p1_stmt)
    p1_record = p1_result.scalar_one_or_none()

    p1_data = None
    if p1_record:
        p1_data = {
            "id": p1_record.id,
            "lot_no_raw": p1_record.lot_no_raw,
            "extras": p1_record.extras,
            "created_at": p1_record.created_at,
        }

    from sqlalchemy.orm import selectinload

    # Fetch P2
    p2_stmt = (
        select(P2Record)
        .options(selectinload(P2Record.items_v2))
        .where(
            P2Record.tenant_id == current_tenant.id, P2Record.lot_no_norm == lot_no_norm
        )
        .order_by(P2Record.winder_number)
    )
    p2_result = await db.execute(p2_stmt)
    p2_records = p2_result.scalars().all()

    p2_data: list[dict[str, Any]] = []
    for r in p2_records:
        items = list(r.items_v2 or [])
        extras: Any = r.extras
        if items:
            extras = _p2_to_query_record_with_items(r, items).additional_data

        p2_data.append(
            {
                "id": r.id,
                "winder_number": r.winder_number,
                "extras": extras,
                "created_at": r.created_at,
            }
        )

    # Fetch P3
    p3_stmt = (
        select(P3Record)
        .options(selectinload(P3Record.items_v2))
        .where(
            P3Record.tenant_id == current_tenant.id, P3Record.lot_no_norm == lot_no_norm
        )
        .order_by(P3Record.production_date_yyyymmdd, P3Record.machine_no)
    )
    p3_result = await db.execute(p3_stmt)
    p3_records = p3_result.scalars().all()

    p3_data: list[dict[str, Any]] = []
    for r in p3_records:
        items = list(r.items_v2 or [])
        extras: Any = r.extras
        if items:
            extras = _p3_to_query_record_with_items(r, items).additional_data

        machine_no = r.machine_no
        mold_no = r.mold_no
        if str(machine_no).upper() == "UNKNOWN" or str(mold_no).upper() == "UNKNOWN":
            derived_machine = None
            derived_mold = None
            if items:
                derived_machine = items[0].machine_no
                derived_mold = items[0].mold_no
            if derived_machine is None or derived_mold is None:
                dm, dmo = _derive_machine_mold_from_extras(r.extras)
                derived_machine = derived_machine or dm
                derived_mold = derived_mold or dmo

            if str(machine_no).upper() == "UNKNOWN":
                machine_no = derived_machine
            if str(mold_no).upper() == "UNKNOWN":
                mold_no = derived_mold

        p3_data.append(
            {
                "id": r.id,
                "production_date": r.production_date_yyyymmdd,
                "machine_no": machine_no,
                "mold_no": mold_no,
                "extras": extras,
                "created_at": r.created_at,
            }
        )

    return TraceDetailResponse(trace_key=trace_key, p1=p1_data, p2=p2_data, p3=p3_data)
