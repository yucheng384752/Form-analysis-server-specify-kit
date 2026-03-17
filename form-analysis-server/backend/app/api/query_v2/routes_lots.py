import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_db
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.utils.normalization import normalize_search_term

from .helpers import (
    _extract_spec_from_row,
    _first_row,
    _yyyymmdd_to_yyyy_mm_dd,
)
from .schemas import LotGroupListV2Compat, LotGroupV2Compat

router = APIRouter()


@router.get("/lots", response_model=LotGroupListV2Compat)
async def query_lot_groups_v2(
    search: str | None = Query(None, description="搜尋批號關鍵字"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> LotGroupListV2Compat:
    """V2 lot grouping (used by legacy fallback; lightweight approximation)."""
    term = (search or "").strip()
    like_term = f"%{term}%" if term else None

    # Aggregate each table separately, then merge in Python.
    p1_stmt = select(
        P1Record.lot_no_norm,
        func.max(P1Record.lot_no_raw).label("lot_no_raw"),
        func.count().label("p1_count"),
        func.max(P1Record.created_at).label("p1_created"),
    ).where(P1Record.tenant_id == current_tenant.id)
    if like_term:
        p1_stmt = p1_stmt.where(P1Record.lot_no_raw.ilike(like_term))
    p1_stmt = p1_stmt.group_by(P1Record.lot_no_norm)

    p2_stmt = select(
        P2Record.lot_no_norm,
        func.max(P2Record.lot_no_raw).label("lot_no_raw"),
        func.count().label("p2_count"),
        func.max(P2Record.created_at).label("p2_created"),
    ).where(P2Record.tenant_id == current_tenant.id)
    if like_term:
        p2_stmt = p2_stmt.where(P2Record.lot_no_raw.ilike(like_term))
    p2_stmt = p2_stmt.group_by(P2Record.lot_no_norm)

    p3_stmt = select(
        P3Record.lot_no_norm,
        func.max(P3Record.lot_no_raw).label("lot_no_raw"),
        func.count().label("p3_count"),
        func.max(P3Record.created_at).label("p3_created"),
        func.max(P3Record.production_date_yyyymmdd).label("latest_prod"),
    ).where(P3Record.tenant_id == current_tenant.id)
    if like_term:
        p3_stmt = p3_stmt.where(P3Record.lot_no_raw.ilike(like_term))
    p3_stmt = p3_stmt.group_by(P3Record.lot_no_norm)

    p1_rows = (await db.execute(p1_stmt)).all()
    p2_rows = (await db.execute(p2_stmt)).all()
    p3_rows = (await db.execute(p3_stmt)).all()

    merged: dict[int, dict[str, Any]] = {}

    def upsert(base: dict[str, Any]) -> None:
        lot_no_norm = int(base["lot_no_norm"])
        if lot_no_norm not in merged:
            merged[lot_no_norm] = {
                "lot_no_norm": lot_no_norm,
                "lot_no": base.get("lot_no_raw") or str(lot_no_norm),
                "p1_count": 0,
                "p2_count": 0,
                "p3_count": 0,
                "latest_production_date": None,
                "created_at": None,
            }
        row = merged[lot_no_norm]
        if base.get("lot_no_raw"):
            row["lot_no"] = base.get("lot_no_raw")
        row["p1_count"] += int(base.get("p1_count") or 0)
        row["p2_count"] += int(base.get("p2_count") or 0)
        row["p3_count"] += int(base.get("p3_count") or 0)

        latest_prod = base.get("latest_prod")
        if latest_prod:
            row["latest_production_date"] = _yyyymmdd_to_yyyy_mm_dd(int(latest_prod))

        created_at = base.get("created_at")
        if created_at is not None:
            row["created_at"] = (
                created_at
                if row["created_at"] is None
                else max(row["created_at"], created_at)
            )

    for lot_no_norm, lot_no_raw, p1_count, p1_created in p1_rows:
        upsert(
            {
                "lot_no_norm": lot_no_norm,
                "lot_no_raw": lot_no_raw,
                "p1_count": p1_count,
                "created_at": p1_created,
            }
        )
    for lot_no_norm, lot_no_raw, p2_count, p2_created in p2_rows:
        upsert(
            {
                "lot_no_norm": lot_no_norm,
                "lot_no_raw": lot_no_raw,
                "p2_count": p2_count,
                "created_at": p2_created,
            }
        )
    for lot_no_norm, lot_no_raw, p3_count, p3_created, latest_prod in p3_rows:
        upsert(
            {
                "lot_no_norm": lot_no_norm,
                "lot_no_raw": lot_no_raw,
                "p3_count": p3_count,
                "created_at": p3_created,
                "latest_prod": latest_prod,
            }
        )

    # Sort and paginate
    groups_raw = list(merged.values())
    groups_raw.sort(
        key=lambda r: (r.get("created_at") is None, r.get("created_at")), reverse=True
    )
    total = len(groups_raw)
    start = (page - 1) * page_size
    end = start + page_size
    page_groups = groups_raw[start:end]

    groups: list[LotGroupV2Compat] = []
    for g in page_groups:
        p1c = int(g.get("p1_count") or 0)
        p2c = int(g.get("p2_count") or 0)
        p3c = int(g.get("p3_count") or 0)
        total_c = p1c + p2c + p3c
        created_iso = (
            g.get("created_at").isoformat()
            if g.get("created_at") is not None
            else "1970-01-01T00:00:00"
        )
        groups.append(
            LotGroupV2Compat(
                lot_no=str(g.get("lot_no") or ""),
                p1_count=p1c,
                p2_count=p2c,
                p3_count=p3c,
                total_count=total_c,
                latest_production_date=g.get("latest_production_date"),
                created_at=created_iso,
            )
        )

    return LotGroupListV2Compat(
        total_count=total, page=page, page_size=page_size, groups=groups
    )


@router.get("/lots/suggestions", response_model=list[str])
async def suggest_lots(
    term: str = Query("", description="lot no prefix/substring"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    t = (term or "").strip()
    if not t:
        return []

    # Search raw lot strings across P1/P2/P3
    like = f"%{t}%"
    p1_stmt = (
        select(P1Record.lot_no_raw)
        .where(
            P1Record.tenant_id == current_tenant.id,
            P1Record.lot_no_raw.ilike(like),
        )
        .limit(limit)
    )
    p2_stmt = (
        select(P2Record.lot_no_raw)
        .where(
            P2Record.tenant_id == current_tenant.id,
            P2Record.lot_no_raw.ilike(like),
        )
        .limit(limit)
    )
    p3_stmt = (
        select(P3Record.lot_no_raw)
        .where(
            P3Record.tenant_id == current_tenant.id,
            P3Record.lot_no_raw.ilike(like),
        )
        .limit(limit)
    )

    lots: list[str] = []
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


@router.get("/options/{field_name}", response_model=list[str])
async def get_field_options_v2(
    field_name: str,
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    field = field_name.strip().lower()
    if field not in {
        "machine_no",
        "mold_no",
        "product_id",
        "specification",
        "winder_number",
        "material",
    }:
        raise HTTPException(status_code=400, detail=f"Unsupported field: {field_name}")

    if field == "material":
        from app.config.constants import get_material_list

        return get_material_list()[:limit]

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
        return [
            str(v[0]).strip() for v in result.fetchall() if v[0] and str(v[0]).strip()
        ]

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
        return [
            str(v[0]).strip() for v in result.fetchall() if v[0] and str(v[0]).strip()
        ]

    if field == "product_id":
        stmt = (
            select(P3Record.product_id)
            .where(P3Record.tenant_id == current_tenant.id)
            .where(P3Record.product_id.isnot(None))
            .distinct()
            .order_by(P3Record.product_id)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [
            str(v[0]).strip() for v in result.fetchall() if v[0] and str(v[0]).strip()
        ]

    # specification: 統一規格選項，從 P1/P2/P3 的 extras 中提取
    if field == "specification":
        # Deduplicate across formatting variants, e.g. "PE32" vs "PE 32" vs "ＰＥ３２".
        # We still return a human-friendly display value (stable by heuristic).
        display_by_key: dict[str, str] = {}

        def _normalize_display(s: str) -> str:
            # NFKC happens in normalize_search_term already; keep a readable form.
            s2 = str(s).strip()
            s2 = re.sub(r"\s+", " ", s2)
            # Make common ASCII tokens consistent (e.g. 'pe 32' -> 'PE 32').
            if re.fullmatch(r"[A-Za-z0-9 _\-\.]+", s2 or ""):
                s2 = s2.upper()
            return s2

        def _score_display(s: str) -> tuple[int, int, int]:
            # Prefer letter + space + digit boundary like 'PE 32'
            boundary_space = 1 if re.search(r"[A-Za-z]+\s+\d", s) else 0
            ascii_only = 1 if all(ord(ch) < 128 for ch in s) else 0
            return (boundary_space, ascii_only, -len(s))

        def _maybe_add_spec(raw: object) -> None:
            if raw is None:
                return
            raw_s = str(raw).strip()
            if not raw_s:
                return
            key = normalize_search_term(raw_s)
            if not key:
                return
            disp = _normalize_display(raw_s)

            existing = display_by_key.get(key)
            if existing is None or _score_display(disp) > _score_display(existing):
                display_by_key[key] = disp

        # P1: extras.Specification
        p1_stmt = (
            select(P1Record.extras)
            .where(P1Record.tenant_id == current_tenant.id)
            .limit(limit)
        )
        p1_result = await db.execute(p1_stmt)
        for (extras,) in p1_result.fetchall():
            if isinstance(extras, dict):
                spec = (
                    extras.get("Specification")
                    or extras.get("specification")
                    or extras.get("規格")
                )
                _maybe_add_spec(spec)

        # P2: extras.format
        p2_stmt = (
            select(P2Record.extras)
            .where(P2Record.tenant_id == current_tenant.id)
            .limit(limit)
        )
        p2_result = await db.execute(p2_stmt)
        for (extras,) in p2_result.fetchall():
            if isinstance(extras, dict):
                spec = (
                    extras.get("format") or extras.get("Format") or extras.get("規格")
                )
                _maybe_add_spec(spec)

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

            _maybe_add_spec(spec)

        specs = sorted(display_by_key.values())
        return specs[:limit]

    # winder_number: 從 P2/P3 的 extras 中提取
    if field == "winder_number":
        winders: list[str] = []
        seen = set()

        # P2: extras.rows[].winder_number
        p2_stmt = (
            select(P2Record.extras)
            .where(P2Record.tenant_id == current_tenant.id)
            .limit(limit)
        )
        p2_result = await db.execute(p2_stmt)
        for (extras,) in p2_result.fetchall():
            if isinstance(extras, dict) and "rows" in extras:
                rows = extras.get("rows", [])
                if isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, dict):
                            winder = (
                                row.get("winder_number")
                                or row.get("Winder Number")
                                or row.get("winder")
                            )
                            if (
                                winder
                                and str(winder).strip()
                                and str(winder).strip() not in seen
                            ):
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
                winder = (
                    row0.get("source_winder")
                    or row0.get("Source Winder")
                    or row0.get("winder")
                )
                if winder and str(winder).strip() and str(winder).strip() not in seen:
                    seen.add(str(winder).strip())
                    winders.append(str(winder).strip())

        winders.sort(key=lambda x: (x.isdigit() and int(x) or 999999, x))
        return winders[:limit]

    return []
