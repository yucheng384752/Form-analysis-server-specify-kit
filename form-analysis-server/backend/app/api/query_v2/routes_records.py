from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import JSON, and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_db, get_request_state_attr
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.services.audit_events import write_audit_event_best_effort
from app.utils.normalization import (
    normalize_lot_no,
    normalize_search_term,
    normalize_search_term_variants,
)

from .helpers import (
    _extract_p2_item_date_yyyymmdd,
    _filter_records_by_production_date_range,
    _merge_p2_records,
    _p1_to_query_record,
    _p2_to_query_record_with_items,
    _p3_to_query_record_with_items,
)
from .schemas import (
    AdvancedSearchRequest,
    AdvancedSearchResponse,
    QueryRecordV2Compat,
    QueryResponseV2Compat,
    TraceResult,
)

router = APIRouter()


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
    if (
        criteria.date_start
        or criteria.date_end
        or criteria.machine_no
        or criteria.mold_no
    ):
        stmt = select(P3Record.lot_no_norm).where(
            P3Record.tenant_id == current_tenant.id
        )

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
            P2Record.winder_number == criteria.winder_number,
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
        stmt = (
            select(P1Record.lot_no_norm)
            .where(P1Record.tenant_id == current_tenant.id)
            .limit(100)
        )
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
        p1_stmt = (
            select(func.count())
            .select_from(P1Record)
            .where(P1Record.tenant_id == current_tenant.id, P1Record.lot_no_norm == lot)
        )
        p1_count = (await db.execute(p1_stmt)).scalar()

        # Count P2
        p2_stmt = (
            select(func.count())
            .select_from(P2Record)
            .where(P2Record.tenant_id == current_tenant.id, P2Record.lot_no_norm == lot)
        )
        p2_count = (await db.execute(p2_stmt)).scalar()

        # Count P3
        p3_stmt = (
            select(func.count())
            .select_from(P3Record)
            .where(P3Record.tenant_id == current_tenant.id, P3Record.lot_no_norm == lot)
        )
        p3_count = (await db.execute(p3_stmt)).scalar()

        results.append(
            TraceResult(
                trace_key=str(lot),
                p1_found=p1_count > 0,
                p2_count=p2_count,
                p3_count=p3_count,
            )
        )

    return AdvancedSearchResponse(total=total, results=results)


@router.get("/records", response_model=QueryResponseV2Compat)
async def query_records_v2(
    lot_no: str | None = Query(None),
    data_type: str | None = Query(None, description="P1|P2|P3"),
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
        material=None,
        specification=None,
        thickness_min=None,
        thickness_max=None,
        winder_number=None,
        data_type=data_type,
        page=page,
        page_size=page_size,
        db=db,
        current_tenant=current_tenant,
    )


@router.get("/records/advanced", response_model=QueryResponseV2Compat)
async def query_records_advanced_v2(
    request: Request = None,
    lot_no: str | None = Query(None),
    production_date_from: str | None = Query(None),
    production_date_to: str | None = Query(None),
    machine_no: list[str] | None = Query(None),
    mold_no: list[str] | None = Query(None),
    product_id: str | None = Query(None),
    material: list[str] | None = Query(None, description="材料代號 (P1/P2)"),
    specification: list[str] | None = Query(
        None, description="統一規格搜尋 (P1.Specification, P2.format, P3.Specification)"
    ),
    thickness_min: int | None = Query(
        None, description="Thickness min (integer, 0.01mm units; e.g., 30 means 0.30mm)"
    ),
    thickness_max: int | None = Query(
        None, description="Thickness max (integer, 0.01mm units; e.g., 33 means 0.33mm)"
    ),
    winder_number: str | None = Query(None, description="Winder Number (P2/P3)"),
    data_type: str | None = Query(None, description="P1|P2|P3"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    dt = (data_type or "").strip().upper() or None
    allow = {"P1", "P2", "P3"}
    if dt and dt not in allow:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    winder_requested: int | None = None
    if winder_number and winder_number.strip():
        try:
            winder_requested = int(winder_number.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid winder_number")

    lot_no_raw = (lot_no or "").strip() or None
    lot_no_norm: int | None
    try:
        lot_no_norm = normalize_lot_no(lot_no_raw) if lot_no_raw else None
    except Exception:
        lot_no_norm = None

    # Parse date range for P3 (YYYY-MM-DD)
    def to_int_yyyymmdd(s: str | None) -> int | None:
        if not s:
            return None
        try:
            return int(date.fromisoformat(s).strftime("%Y%m%d"))
        except Exception:
            return None

    date_from_i = to_int_yyyymmdd(production_date_from)
    date_to_i = to_int_yyyymmdd(production_date_to)

    machine_terms = [
        s.strip() for s in (machine_no or []) if isinstance(s, str) and s.strip()
    ]
    mold_terms = [
        s.strip() for s in (mold_no or []) if isinstance(s, str) and s.strip()
    ]
    material_terms = [
        s.strip() for s in (material or []) if isinstance(s, str) and s.strip()
    ]
    specification_terms = [
        s.strip() for s in (specification or []) if isinstance(s, str) and s.strip()
    ]

    # AND semantics for multi-select within the same field.
    material_norms = [normalize_search_term(s) for s in material_terms]
    material_norms = [s for s in material_norms if s]
    specification_norms = [normalize_search_term(s) for s in specification_terms]
    specification_norms = [s for s in specification_norms if s]

    thickness_min_i = thickness_min
    thickness_max_i = thickness_max
    if thickness_min_i is not None and thickness_max_i is None:
        thickness_max_i = thickness_min_i
    if thickness_max_i is not None and thickness_min_i is None:
        thickness_min_i = thickness_max_i

    thickness_min_f: float | None = None
    thickness_max_f: float | None = None
    if thickness_min_i is not None and thickness_max_i is not None:
        if thickness_min_i > thickness_max_i:
            raise HTTPException(status_code=400, detail="Invalid thickness range")
        # Input unit: 0.01mm integers (e.g., 30 -> 0.30mm)
        thickness_min_f = float(thickness_min_i) / 100.0
        thickness_max_f = float(thickness_max_i) / 100.0

    records: list[QueryRecordV2Compat] = []

    dialect_name = (db.get_bind().dialect.name if db.get_bind() else "").lower()

    def _canon_sql(expr):
        """Best-effort canonicalization for SQL text expressions.

        Removes common separators and lowercases the string so we can match
        user input normalized by normalize_search_term().
        """
        s = func.coalesce(expr, "")
        s = func.lower(s)
        for ch in [
            " ",
            "\t",
            "\n",
            "\r",
            "_",
            "-",
            "‐",
            "‑",
            "–",
            "—",
            "－",
            "　",
        ]:
            s = func.replace(s, ch, "")
        return s

    def _escape_like(term: str) -> str:
        return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _normalized_like(expr, term_obj: object):
        variants = normalize_search_term_variants(term_obj)
        if not variants:
            return None
        preds = []
        for v in variants:
            preds.append(_canon_sql(expr).like(f"%{_escape_like(v)}%", escape="\\"))
        return or_(*preds)

    def _json_key_text(col, key: str):
        if dialect_name == "postgresql":
            return func.jsonb_extract_path_text(cast(col, JSONB), key)
        # SQLite test DB uses JSON1 extension functions
        return func.json_extract(cast(col, JSON), f"$.{key}")

    # P1
    # winder_number 僅適用 P2/P3：即使 data_type=P1，也不應在指定 winder_number 時回傳 P1。
    if (dt == "P1" and winder_requested is None) or (
        dt is None and winder_requested is None
    ):
        p1_stmt = select(P1Record).where(P1Record.tenant_id == current_tenant.id)
        if lot_no_norm is not None:
            p1_stmt = p1_stmt.where(P1Record.lot_no_norm == lot_no_norm)
        elif lot_no_raw:
            p1_stmt = p1_stmt.where(P1Record.lot_no_raw.ilike(f"%{lot_no_raw}%"))

        # 統一規格搜尋: P1 查 extras.Specification
        for spec in specification_terms:
            preds = [
                _normalized_like(
                    _json_key_text(P1Record.extras, "Specification"), spec
                ),
                _normalized_like(
                    _json_key_text(P1Record.extras, "specification"), spec
                ),
                _normalized_like(_json_key_text(P1Record.extras, "規格"), spec),
            ]
            preds = [p for p in preds if p is not None]
            if preds:
                p1_stmt = p1_stmt.where(or_(*preds))

        p1_stmt = p1_stmt.order_by(P1Record.created_at.desc()).limit(page * page_size)
        p1_result = await db.execute(p1_stmt)
        records.extend([_p1_to_query_record(r) for r in p1_result.scalars().all()])

    # P2
    if dt in (None, "P2"):
        from sqlalchemy.orm import selectinload

        from app.models.p2_item_v2 import P2ItemV2

        # 查詢 P2Record，預先加載 items_v2
        p2_stmt = (
            select(P2Record)
            .options(selectinload(P2Record.items_v2))
            .where(P2Record.tenant_id == current_tenant.id)
        )
        if lot_no_norm is not None:
            p2_stmt = p2_stmt.where(P2Record.lot_no_norm == lot_no_norm)
        elif lot_no_raw:
            p2_stmt = p2_stmt.where(P2Record.lot_no_raw.ilike(f"%{lot_no_raw}%"))

        # 統一規格搜尋: 在 items 的 row_data 中搜尋
        # NOTE: SQLite's JSON/LIKE canonicalization is less reliable across environments.
        # For sqlite, we rely on Python-side item pruning (still correct, test-friendly).
        if specification_terms and dialect_name != "sqlite":
            # 需要 JOIN p2_items_v2 來篩選
            p2_stmt = p2_stmt.join(P2ItemV2, P2Record.id == P2ItemV2.p2_record_id)
            for spec in specification_terms:
                preds = [
                    _normalized_like(_json_key_text(P2ItemV2.row_data, "format"), spec),
                    _normalized_like(_json_key_text(P2ItemV2.row_data, "Format"), spec),
                    _normalized_like(_json_key_text(P2ItemV2.row_data, "規格"), spec),
                ]
                preds = [p for p in preds if p is not None]
                if preds:
                    p2_stmt = p2_stmt.where(or_(*preds))
            p2_stmt = p2_stmt.distinct()

        p2_stmt = p2_stmt.order_by(P2Record.created_at.desc())
        p2_result = await db.execute(p2_stmt)
        p2_records = p2_result.scalars().unique().all()

        def _p2_item_matches_spec(item: Any) -> bool:
            if not specification_norms:
                return True
            raw = (
                item.row_data
                if isinstance(getattr(item, "row_data", None), dict)
                else {}
            )
            haystacks: list[str] = []
            for key in ["format", "Format", "規格", "specification", "Specification"]:
                v = raw.get(key)
                v_norm = normalize_search_term(v)
                if v_norm:
                    haystacks.append(v_norm)
            # AND semantics: every selected spec must match.
            return all(
                any(spec_norm in h for h in haystacks)
                for spec_norm in specification_norms
            )

        def _p2_item_matches_material(item: Any) -> bool:
            if not material_norms:
                return True
            raw = (
                item.row_data
                if isinstance(getattr(item, "row_data", None), dict)
                else {}
            )
            haystacks: list[str] = []
            for key in [
                "material_code",
                "Material",
                "Material Code",
                "material",
                "材料",
                "材料代號",
            ]:
                v = raw.get(key)
                v_norm = normalize_search_term(v)
                if v_norm:
                    haystacks.append(v_norm)
            return all(
                any(mat_norm in h for h in haystacks) for mat_norm in material_norms
            )

        def _p2_item_matches_thickness(item: Any) -> bool:
            if thickness_min_f is None or thickness_max_f is None:
                return True
            # OR semantics across thickness1..7: any measurement in range qualifies.
            # Null values are treated as non-matching.
            for field in [
                "thickness1",
                "thickness2",
                "thickness3",
                "thickness4",
                "thickness5",
                "thickness6",
                "thickness7",
            ]:
                v = getattr(item, field, None)
                if v is None:
                    continue
                try:
                    vf = float(v)
                except Exception:
                    continue
                if thickness_min_f <= vf <= thickness_max_f:
                    return True
            return False

        legacy_records: list[P2Record] = []
        # When P2 is stored as 1 record per winder (current v2 schema), advanced
        # queries should still return ONE card per lot (like basic search).
        # We therefore merge items across winders by lot_no_norm.
        p2_items_by_lot: dict[int, list[Any]] = {}
        p2_best_record_by_lot: dict[int, P2Record] = {}

        # 處理每個 P2Record + 其 items_v2；若沒有 items_v2，走 legacy merge/fallback
        for p2_record in p2_records:
            items = list(p2_record.items_v2 or [])

            # 套用 winder 篩選（items 層級）
            if winder_requested is not None:
                items = [
                    item for item in items if item.winder_number == winder_requested
                ]

            # 進階查詢時，只顯示與搜尋條件相關的 row（避免 UI 展開看到一堆不相關 rows）。
            if specification_norms:
                items = [item for item in items if _p2_item_matches_spec(item)]
            if material_norms:
                items = [item for item in items if _p2_item_matches_material(item)]
            if thickness_min_f is not None and thickness_max_f is not None:
                items = [item for item in items if _p2_item_matches_thickness(item)]

            if items:
                lot_key = int(p2_record.lot_no_norm)
                p2_items_by_lot.setdefault(lot_key, []).extend(items)

                best = p2_best_record_by_lot.get(lot_key)
                if best is None or (
                    getattr(p2_record, "created_at", None)
                    and p2_record.created_at > best.created_at
                ):
                    p2_best_record_by_lot[lot_key] = p2_record
                continue

            # If we had items originally but they were pruned by row-level filters,
            # do NOT fall back to legacy record shapes.
            if list(p2_record.items_v2 or []):
                continue

            # Legacy: 沒有 items_v2 的 P2Record 可能仍以 extras 方式保存
            if winder_requested is not None:
                if p2_record.winder_number != winder_requested:
                    continue
            legacy_records.append(p2_record)

        # Merge items-based P2 results into one card per lot.
        for lot_key, items in p2_items_by_lot.items():
            best = p2_best_record_by_lot.get(lot_key)
            if not best:
                continue
            records.append(_p2_to_query_record_with_items(best, items))

        if legacy_records:
            records.extend(_merge_p2_records(legacy_records))

    # P3
    if dt in (None, "P3"):
        from sqlalchemy.orm import selectinload

        from app.models.p3_item_v2 import P3ItemV2

        # 查詢 P3Record，預先加載 items_v2
        p3_stmt = (
            select(P3Record)
            .options(selectinload(P3Record.items_v2))
            .where(P3Record.tenant_id == current_tenant.id)
        )
        if lot_no_norm is not None:
            p3_stmt = p3_stmt.where(P3Record.lot_no_norm == lot_no_norm)
        elif lot_no_raw:
            p3_stmt = p3_stmt.where(P3Record.lot_no_raw.ilike(f"%{lot_no_raw}%"))
        if date_from_i is not None:
            p3_stmt = p3_stmt.where(P3Record.production_date_yyyymmdd >= date_from_i)
        if date_to_i is not None:
            p3_stmt = p3_stmt.where(P3Record.production_date_yyyymmdd <= date_to_i)
        for term in machine_terms:
            pred = _normalized_like(P3Record.machine_no, term)
            if pred is not None:
                p3_stmt = p3_stmt.where(pred)
        for term in mold_terms:
            pred = _normalized_like(P3Record.mold_no, term)
            if pred is not None:
                p3_stmt = p3_stmt.where(pred)
        if product_id and product_id.strip():
            pred = _normalized_like(P3Record.product_id, product_id)
            if pred is not None:
                p3_stmt = p3_stmt.where(pred)

        # 統一規格搜尋: 在 items 的 specification 欄位中搜尋
        if specification_terms:
            p3_stmt = p3_stmt.join(P3ItemV2, P3Record.id == P3ItemV2.p3_record_id)
            for spec in specification_terms:
                pred = _normalized_like(P3ItemV2.specification, spec)
                if pred is not None:
                    p3_stmt = p3_stmt.where(pred)
            p3_stmt = p3_stmt.distinct()

        # Winder Number 篩選: 搜尋 items 的 source_winder
        if winder_requested is not None:
            if not specification:  # 避免重複 JOIN
                p3_stmt = p3_stmt.join(P3ItemV2, P3Record.id == P3ItemV2.p3_record_id)
            p3_stmt = p3_stmt.where(
                P3ItemV2.source_winder == winder_requested
            ).distinct()

        p3_stmt = p3_stmt.order_by(P3Record.created_at.desc())
        p3_result = await db.execute(p3_stmt)
        p3_records = p3_result.scalars().unique().all()

        # 處理每個 P3Record + 其 items
        for p3_record in p3_records:
            items = list(p3_record.items_v2 or [])

            # 進階查詢時，只顯示與搜尋條件相關的 rows。
            if winder_requested is not None:
                items = [
                    item for item in items if item.source_winder == winder_requested
                ]
            if specification_norms:

                def _p3_item_matches_spec(item: Any) -> bool:
                    v_norm = (
                        normalize_search_term(getattr(item, "specification", None))
                        or ""
                    )
                    return all(spec_norm in v_norm for spec_norm in specification_norms)

                items = [item for item in items if _p3_item_matches_spec(item)]
            if material_norms:

                def _p3_item_matches_material(item: Any) -> bool:
                    raw = (
                        item.row_data
                        if isinstance(getattr(item, "row_data", None), dict)
                        else {}
                    )
                    haystacks: list[str] = []
                    for key in [
                        "material_code",
                        "Material",
                        "Material Code",
                        "material",
                        "材料",
                        "材料代號",
                    ]:
                        v = raw.get(key)
                        v_norm = normalize_search_term(v)
                        if v_norm:
                            haystacks.append(v_norm)
                    return all(
                        any(mat_norm in h for h in haystacks)
                        for mat_norm in material_norms
                    )

                items = [item for item in items if _p3_item_matches_material(item)]

            if items:  # 只有有 items 的才顯示
                records.append(_p3_to_query_record_with_items(p3_record, items))

    if material_norms:
        material_keys = (
            "material_code",
            "Material",
            "Material Code",
            "material",
            "材料",
            "材料代號",
        )

        def _matches_material(rec: QueryRecordV2Compat) -> bool:
            data = rec.additional_data
            candidates: list[str] = []
            if isinstance(data, dict):
                for k in material_keys:
                    v = data.get(k)
                    if v is not None and str(v).strip():
                        candidates.append(str(v).strip())
                rows = data.get("rows")
                if isinstance(rows, list):
                    matched_rows: list[dict[str, Any]] = []
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        row_candidates: list[str] = []
                        for k in material_keys:
                            v = row.get(k)
                            if v is not None and str(v).strip():
                                row_candidates.append(str(v).strip())
                                candidates.append(str(v).strip())

                        # Prune rows to only relevant ones for advanced searches.
                        if row_candidates:
                            if any(
                                (
                                    (normalize_search_term(c) or "")
                                    and all(
                                        mat_norm in (normalize_search_term(c) or "")
                                        for mat_norm in material_norms
                                    )
                                )
                                for c in row_candidates
                            ):
                                matched_rows.append(row)

                    if matched_rows:
                        rec.additional_data = {**data, "rows": matched_rows}

            for c in candidates:
                c_norm = normalize_search_term(c)
                if not c_norm:
                    continue
                if all(mat_norm in c_norm for mat_norm in material_norms):
                    return True
            return False

        records = [r for r in records if _matches_material(r)]

    records = _filter_records_by_production_date_range(records, date_from_i, date_to_i)

    # Sort and paginate in memory (simple, OK for current UI)
    records.sort(key=lambda r: r.created_at, reverse=True)
    total_count = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    page_records = records[start:end]

    # Optional semantic audit event for advanced queries.
    # Avoids logging empty/no-op queries to reduce noise.
    filters: dict[str, Any] = {}
    if lot_no_raw:
        filters["lot_no"] = lot_no_raw
    if date_from_i is not None:
        filters["production_date_from"] = int(date_from_i)
    if date_to_i is not None:
        filters["production_date_to"] = int(date_to_i)
    if machine_terms:
        filters["machine_no"] = machine_terms
    if mold_terms:
        filters["mold_no"] = mold_terms
    if product_id and product_id.strip():
        filters["product_id"] = product_id.strip()
    if material_terms:
        filters["material"] = material_terms
    if specification_terms:
        filters["specification"] = specification_terms
    if winder_requested is not None:
        filters["winder_number"] = int(winder_requested)
    if thickness_min_i is not None:
        filters["thickness_min"] = int(thickness_min_i)
    if thickness_max_i is not None:
        filters["thickness_max"] = int(thickness_max_i)
    if dt:
        filters["data_type"] = dt

    if request is not None and filters:
        actor_api_key_id = getattr(
            getattr(request, "state", None), "auth_api_key_id", None
        )
        actor_api_key_label = getattr(
            getattr(request, "state", None), "auth_api_key_label", None
        )
        request_id = get_request_state_attr(request, "request_id")
        await write_audit_event_best_effort(
            tenant_id=current_tenant.id,
            actor_api_key_id=actor_api_key_id,
            actor_label_snapshot=actor_api_key_label,
            request_id=str(request_id) if request_id else None,
            method=request.method,
            path=request.url.path,
            status_code=200,
            action="query.advanced",
            metadata={
                "filters": filters,
                "page": int(page),
                "page_size": int(page_size),
                "total_count": int(total_count),
                "returned_count": int(len(page_records)),
            },
            client_host=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return QueryResponseV2Compat(
        total_count=total_count,
        page=page,
        page_size=page_size,
        records=page_records,
    )
