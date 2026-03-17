from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import JSON, and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_db, get_request_state_attr
from app.models.core.tenant import Tenant
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.services.audit_events import write_audit_event_best_effort
from app.utils.normalization import (
    normalize_lot_no,
    normalize_search_term,
    normalize_search_term_variants,
)

from .helpers import (
    _coerce_row_data_terms,
    _extract_p2_item_date_yyyymmdd,
    _extract_p2_item_slitting_result,
    _filter_records_by_production_date_range,
    _merge_p2_records,
    _p2_to_query_record_with_items,
    _p3_to_query_record_with_items,
    _row_data_key_aliases,
    _row_data_value_matches,
    _validate_row_data_key,
)
from .routes_records import query_records_advanced_v2
from .schemas import (
    DynamicQueryRequest,
    QueryRecordV2Compat,
    QueryResponseV2Compat,
)

router = APIRouter()


@router.post("/records/dynamic", response_model=QueryResponseV2Compat)
async def query_records_dynamic_v2(
    body: DynamicQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Dynamic query (allowlisted) -> translated to /records/advanced.

    Goal: provide a safe foundation for a query-builder UI without exposing arbitrary
    SQL/JSON-path querying. Unknown fields/operators are rejected with 400.
    """

    dt = (body.data_type or "").strip().upper() or None
    if dt and dt not in {"P1", "P2", "P3"}:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    # Field allowlist and operator allowlist.
    # Keep this intentionally small; expand via explicit review.
    field_ops: dict[str, set[str]] = {
        "lot_no": {"contains", "eq"},
        "production_date": {"eq", "between", "gte", "lte"},
        "machine_no": {"contains", "all_of"},
        "mold_no": {"contains", "all_of"},
        "product_id": {"contains"},
        "material": {"all_of"},
        "specification": {"all_of"},
        "winder_number": {"eq"},
        "slitting_result": {"eq"},
        "thickness": {"between"},
    }
    row_data_ops = {"contains", "eq", "all_of"}
    compatible_fields_by_data_type: dict[str, set[str]] = {
        # P1 table supports lot/spec only in current implementation.
        "P1": {"lot_no", "specification"},
        # P2 data is item-centric; machine/mold/product are not available filters.
        # production_date is supported for analytics date-range queries.
        "P2": {
            "lot_no",
            "production_date",
            "specification",
            "material",
            "winder_number",
            "slitting_result",
            "thickness",
        },
        # P3 supports station-level and item-level filters, but not thickness.
        "P3": {
            "lot_no",
            "production_date",
            "machine_no",
            "mold_no",
            "product_id",
            "material",
            "specification",
            "winder_number",
        },
    }

    # Accumulate translated advanced-query params.
    lot_no: str | None = None
    production_date_from: str | None = None
    production_date_to: str | None = None
    machine_no: list[str] | None = None
    mold_no: list[str] | None = None
    product_id: str | None = None
    material: list[str] | None = None
    specification: list[str] | None = None
    thickness_min: int | None = None
    thickness_max: int | None = None
    winder_number: str | None = None
    slitting_result: float | None = None
    row_data_filters: list[dict[str, Any]] = []
    requested_fields: set[str] = set()

    def _as_str_list(v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            return [s] if s else []
        if isinstance(v, list):
            out: list[str] = []
            for item in v:
                if isinstance(item, str):
                    s = item.strip()
                    if s:
                        out.append(s)
                else:
                    out.append(str(item))
            return [s for s in out if s]
        return [str(v).strip()] if str(v).strip() else []

    def _as_int_pair(v: Any) -> tuple[int, int]:
        if isinstance(v, dict):
            v = [v.get("min"), v.get("max")]
        if not isinstance(v, list) or len(v) != 2:
            raise HTTPException(
                status_code=400, detail="Invalid thickness value; expected [min,max]"
            )
        try:
            a = int(v[0])
            b = int(v[1])
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid thickness value; expected integers"
            )
        return a, b

    def _as_date_pair(v: Any) -> tuple[str | None, str | None]:
        if isinstance(v, dict):
            v = [v.get("from"), v.get("to")]
        if isinstance(v, list):
            if len(v) != 2:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid production_date; expected [from,to]",
                )
            return (
                str(v[0]).strip() if v[0] is not None and str(v[0]).strip() else None,
                str(v[1]).strip() if v[1] is not None and str(v[1]).strip() else None,
            )
        s = str(v).strip() if v is not None else None
        return (s, s) if s else (None, None)

    for f in body.filters or []:
        field = (getattr(f, "field", "") or "").strip()
        op = (getattr(f, "op", "") or "").strip().lower()

        if field.startswith("row_data."):
            key = _validate_row_data_key(field[len("row_data.") :])
            if op not in row_data_ops:
                raise HTTPException(
                    status_code=400, detail=f"Invalid operator for row_data.{key}: {op}"
                )
            row_data_filters.append({"key": key, "op": op, "value": f.value})
            continue

        if not field or field not in field_ops:
            raise HTTPException(status_code=400, detail=f"Invalid field: {field}")
        if op not in field_ops[field]:
            raise HTTPException(
                status_code=400, detail=f"Invalid operator for {field}: {op}"
            )
        requested_fields.add(field)

        if field == "lot_no":
            if lot_no is not None:
                raise HTTPException(status_code=400, detail="Duplicate lot_no filter")
            if not isinstance(f.value, str) or not f.value.strip():
                raise HTTPException(status_code=400, detail="Invalid lot_no value")
            if op == "eq":
                # Enforce normalize-able lot number for deterministic equality.
                try:
                    _ = normalize_lot_no(f.value.strip())
                except Exception:
                    raise HTTPException(
                        status_code=400, detail="lot_no eq requires a valid lot number"
                    )
            lot_no = f.value.strip()

        elif field == "production_date":
            if op == "between":
                a, b = _as_date_pair(f.value)
                if not a or not b:
                    raise HTTPException(
                        status_code=400,
                        detail="production_date between requires [from,to]",
                    )
                production_date_from = a
                production_date_to = b
            elif op == "eq":
                a, b = _as_date_pair(f.value)
                if not a:
                    raise HTTPException(
                        status_code=400, detail="production_date eq requires a date"
                    )
                production_date_from = a
                production_date_to = b
            elif op == "gte":
                s = str(f.value).strip() if f.value is not None else ""
                if not s:
                    raise HTTPException(
                        status_code=400, detail="production_date gte requires a date"
                    )
                production_date_from = s
            elif op == "lte":
                s = str(f.value).strip() if f.value is not None else ""
                if not s:
                    raise HTTPException(
                        status_code=400, detail="production_date lte requires a date"
                    )
                production_date_to = s

        elif field == "machine_no":
            terms = _as_str_list(f.value)
            if not terms:
                raise HTTPException(status_code=400, detail="Invalid machine_no value")
            machine_no = (machine_no or []) + terms

        elif field == "mold_no":
            terms = _as_str_list(f.value)
            if not terms:
                raise HTTPException(status_code=400, detail="Invalid mold_no value")
            mold_no = (mold_no or []) + terms

        elif field == "product_id":
            if product_id is not None:
                raise HTTPException(
                    status_code=400, detail="Duplicate product_id filter"
                )
            if not isinstance(f.value, str) or not f.value.strip():
                raise HTTPException(status_code=400, detail="Invalid product_id value")
            product_id = f.value.strip()

        elif field == "material":
            terms = _as_str_list(f.value)
            if not terms:
                raise HTTPException(status_code=400, detail="Invalid material value")
            material = (material or []) + terms

        elif field == "specification":
            terms = _as_str_list(f.value)
            if not terms:
                raise HTTPException(
                    status_code=400, detail="Invalid specification value"
                )
            specification = (specification or []) + terms

        elif field == "winder_number":
            if winder_number is not None:
                raise HTTPException(
                    status_code=400, detail="Duplicate winder_number filter"
                )
            try:
                w = int(f.value)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Invalid winder_number value"
                )
            winder_number = str(w)

        elif field == "slitting_result":
            if slitting_result is not None:
                raise HTTPException(
                    status_code=400, detail="Duplicate slitting_result filter"
                )
            try:
                slitting_result = float(f.value)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Invalid slitting_result value"
                )

        elif field == "thickness":
            if thickness_min is not None or thickness_max is not None:
                raise HTTPException(
                    status_code=400, detail="Duplicate thickness filter"
                )
            a, b = _as_int_pair(f.value)
            thickness_min = a
            thickness_max = b

    if dt is not None:
        unsupported = sorted(
            field
            for field in requested_fields
            if field not in compatible_fields_by_data_type[dt]
        )
        if unsupported:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported field(s) for data_type {dt}: "
                    + ", ".join(unsupported)
                ),
            )

    # If caller doesn't specify data_type, keep behavior aligned with GET /records/advanced.
    # row_data filters require an explicit station because P1 has no row_data.
    if dt is None:
        if row_data_filters:
            raise HTTPException(
                status_code=400,
                detail="row_data filters require explicit data_type (P2 or P3)",
            )

        resp = await query_records_advanced_v2(
            request=request,
            lot_no=lot_no,
            production_date_from=production_date_from,
            production_date_to=production_date_to,
            machine_no=machine_no,
            mold_no=mold_no,
            product_id=product_id,
            material=material,
            specification=specification,
            thickness_min=thickness_min,
            thickness_max=thickness_max,
            winder_number=winder_number,
            data_type=None,
            page=body.page,
            page_size=body.page_size,
            db=db,
            current_tenant=current_tenant,
        )

        if request is not None and (body.filters or row_data_filters):
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
                action="query.dynamic",
                metadata={
                    "data_type": None,
                    "filters": [f.model_dump() for f in (body.filters or [])],
                    "row_data_filters": row_data_filters,
                    "page": int(body.page),
                    "page_size": int(body.page_size),
                    "total_count": int(resp.total_count),
                    "returned_count": int(len(resp.records)),
                },
                client_host=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )

        return resp

    # From here on, run the query in-process so row_data filters apply BEFORE pagination.
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
        thickness_min_f = float(thickness_min_i) / 100.0
        thickness_max_f = float(thickness_max_i) / 100.0

    dialect_name = (db.get_bind().dialect.name if db.get_bind() else "").lower()

    def _canon_sql(expr):
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
        return func.json_extract(cast(col, JSON), f"$.{key}")

    def _row_data_sql_predicates(row_data_col, key: str, op: str, value: Any):
        keys = _row_data_key_aliases(key)
        if not keys:
            return None

        preds: list[Any] = []
        for row_key in keys:
            expr = _json_key_text(row_data_col, row_key)
            if op == "contains":
                pred = _normalized_like(expr, value)
                if pred is not None:
                    preds.append(pred)
                continue

            if op == "eq":
                variants = normalize_search_term_variants(value)
                variants = [v for v in variants if v]
                if not variants:
                    continue
                preds.append(or_(*[_canon_sql(expr) == v for v in variants]))
                continue

            if op == "all_of":
                terms = _coerce_row_data_terms(value)
                norms = [normalize_search_term(t) for t in terms]
                norms = [n for n in norms if n]
                if not norms:
                    continue
                preds.append(
                    and_(*[_canon_sql(expr).like(f"%{_escape_like(n)}%", escape="\\") for n in norms])
                )
                continue

        if not preds:
            return None
        return or_(*preds) if len(preds) > 1 else preds[0]

    def _row_data_item_matches(item: Any, key: str, op: str, value: Any) -> bool:
        raw = item.row_data if isinstance(getattr(item, "row_data", None), dict) else {}
        if not isinstance(raw, dict):
            return False
        aliases = _row_data_key_aliases(key)
        if not aliases:
            return False

        raw_lookup = {
            (str(raw_key).strip().lower()): raw_value
            for raw_key, raw_value in raw.items()
            if isinstance(raw_key, str) and raw_key.strip()
        }

        for alias_key in aliases:
            v = raw.get(alias_key)
            if v is None:
                v = raw_lookup.get(alias_key.strip().lower())
            if v is None:
                continue
            if _row_data_value_matches(v, op, value):
                return True

        return False

    for rf in row_data_filters:
        key = _validate_row_data_key(str(rf.get("key") or ""))
        op = str(rf.get("op") or "").strip().lower()
        if op not in row_data_ops:
            raise HTTPException(
                status_code=400, detail=f"Invalid operator for row_data.{key}: {op}"
            )

    records: list[QueryRecordV2Compat] = []

    if dt == "P1":
        if row_data_filters:
            raise HTTPException(
                status_code=400, detail="row_data filters are not supported for P1"
            )
        # Delegate to existing advanced logic (P1 only) by calling GET handler in-process.
        resp = await query_records_advanced_v2(
            request=request,
            lot_no=lot_no,
            production_date_from=production_date_from,
            production_date_to=production_date_to,
            machine_no=machine_no,
            mold_no=mold_no,
            product_id=product_id,
            material=material,
            specification=specification,
            thickness_min=thickness_min,
            thickness_max=thickness_max,
            winder_number=winder_number,
            data_type=dt,
            page=body.page,
            page_size=body.page_size,
            db=db,
            current_tenant=current_tenant,
        )
        return resp

    if dt == "P2":
        from sqlalchemy.orm import selectinload

        from app.models.p2_item_v2 import P2ItemV2

        p2_stmt = (
            select(P2Record)
            .options(selectinload(P2Record.items_v2))
            .where(P2Record.tenant_id == current_tenant.id)
        )
        if lot_no_norm is not None:
            p2_stmt = p2_stmt.where(P2Record.lot_no_norm == lot_no_norm)
        elif lot_no_raw:
            p2_stmt = p2_stmt.where(P2Record.lot_no_raw.ilike(f"%{lot_no_raw}%"))

        if (
            specification_terms
            or row_data_filters
            or slitting_result is not None
        ) and dialect_name != "sqlite":
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

            for rf in row_data_filters:
                pred = _row_data_sql_predicates(
                    P2ItemV2.row_data,
                    str(rf.get("key")),
                    str(rf.get("op")),
                    rf.get("value"),
                )
                if pred is not None:
                    p2_stmt = p2_stmt.where(pred)

            if slitting_result is not None:
                p2_stmt = p2_stmt.where(P2ItemV2.slitting_result == slitting_result)

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

        def _p2_item_matches_slitting_result(item: Any) -> bool:
            if slitting_result is None:
                return True
            actual = _extract_p2_item_slitting_result(item)
            if actual is None:
                return False
            try:
                return float(actual) == slitting_result
            except Exception:
                return False

        def _p2_item_matches_row_data(item: Any) -> bool:
            if not row_data_filters:
                return True
            for rf in row_data_filters:
                if not _row_data_item_matches(
                    item, str(rf.get("key")), str(rf.get("op")), rf.get("value")
                ):
                    return False
            return True

        def _p2_item_matches_date(item: Any) -> bool:
            if date_from_i is None and date_to_i is None:
                return True
            ymd = _extract_p2_item_date_yyyymmdd(item)
            if ymd is None:
                return False
            if date_from_i is not None and ymd < date_from_i:
                return False
            if date_to_i is not None and ymd > date_to_i:
                return False
            return True

        p2_items_by_lot: dict[int, list[Any]] = {}
        p2_best_record_by_lot: dict[int, P2Record] = {}
        legacy_records: list[P2Record] = []

        for p2_record in p2_records:
            items = list(p2_record.items_v2 or [])
            if winder_requested is not None:
                items = [
                    item for item in items if item.winder_number == winder_requested
                ]
            if date_from_i is not None or date_to_i is not None:
                items = [item for item in items if _p2_item_matches_date(item)]
            if specification_norms:
                items = [item for item in items if _p2_item_matches_spec(item)]
            if material_norms:
                items = [item for item in items if _p2_item_matches_material(item)]
            if thickness_min_f is not None and thickness_max_f is not None:
                items = [item for item in items if _p2_item_matches_thickness(item)]
            if slitting_result is not None:
                items = [item for item in items if _p2_item_matches_slitting_result(item)]
            if row_data_filters:
                items = [item for item in items if _p2_item_matches_row_data(item)]

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

            if list(p2_record.items_v2 or []):
                continue

            if winder_requested is not None:
                if p2_record.winder_number != winder_requested:
                    continue
            legacy_records.append(p2_record)

        for lot_key, items in p2_items_by_lot.items():
            best = p2_best_record_by_lot.get(lot_key)
            if not best:
                continue
            records.append(_p2_to_query_record_with_items(best, items))
        if legacy_records:
            records.extend(_merge_p2_records(legacy_records))

    if dt == "P3":
        from sqlalchemy.orm import selectinload

        from app.models.p3_item_v2 import P3ItemV2

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

        if (
            specification_terms or (winder_requested is not None) or row_data_filters
        ) and dialect_name != "sqlite":
            p3_stmt = p3_stmt.join(P3ItemV2, P3Record.id == P3ItemV2.p3_record_id)

            if specification_terms:
                for spec in specification_terms:
                    pred = _normalized_like(P3ItemV2.specification, spec)
                    if pred is not None:
                        p3_stmt = p3_stmt.where(pred)

            if winder_requested is not None:
                p3_stmt = p3_stmt.where(P3ItemV2.source_winder == winder_requested)

            for rf in row_data_filters:
                pred = _row_data_sql_predicates(
                    P3ItemV2.row_data,
                    str(rf.get("key")),
                    str(rf.get("op")),
                    rf.get("value"),
                )
                if pred is not None:
                    p3_stmt = p3_stmt.where(pred)

            p3_stmt = p3_stmt.distinct()

        p3_stmt = p3_stmt.order_by(P3Record.created_at.desc())
        p3_result = await db.execute(p3_stmt)
        p3_records = p3_result.scalars().unique().all()

        def _p3_item_matches_spec(item: Any) -> bool:
            if not specification_norms:
                return True
            v_norm = normalize_search_term(getattr(item, "specification", None)) or ""
            return all(spec_norm in v_norm for spec_norm in specification_norms)

        def _p3_item_matches_material(item: Any) -> bool:
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

        def _p3_item_matches_row_data(item: Any) -> bool:
            if not row_data_filters:
                return True
            for rf in row_data_filters:
                if not _row_data_item_matches(
                    item, str(rf.get("key")), str(rf.get("op")), rf.get("value")
                ):
                    return False
            return True

        for p3_record in p3_records:
            items = list(p3_record.items_v2 or [])
            if winder_requested is not None:
                items = [
                    item for item in items if item.source_winder == winder_requested
                ]
            if specification_norms:
                items = [item for item in items if _p3_item_matches_spec(item)]
            if material_norms:
                items = [item for item in items if _p3_item_matches_material(item)]
            if row_data_filters:
                items = [item for item in items if _p3_item_matches_row_data(item)]

            if items:
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

    records.sort(key=lambda r: r.created_at, reverse=True)
    total_count = len(records)
    start = (body.page - 1) * body.page_size
    end = start + body.page_size
    page_records = records[start:end]

    if request is not None and (body.filters or row_data_filters):
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
            action="query.dynamic",
            metadata={
                "data_type": dt,
                "filters": [f.model_dump() for f in (body.filters or [])],
                "row_data_filters": row_data_filters,
                "page": int(body.page),
                "page_size": int(body.page_size),
                "total_count": int(total_count),
                "returned_count": int(len(page_records)),
            },
            client_host=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return QueryResponseV2Compat(
        total_count=total_count,
        page=body.page,
        page_size=body.page_size,
        records=page_records,
    )
