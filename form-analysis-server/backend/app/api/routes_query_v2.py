import re
from collections.abc import Iterable
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import JSON, and_, cast, func, or_, select, union_all
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

router = APIRouter()

# --- Schemas ---


class AdvancedSearchRequest(BaseModel):
    lot_no: str | None = None
    date_start: date | None = None
    date_end: date | None = None
    machine_no: str | None = None
    mold_no: str | None = None
    winder_number: int | None = None

    page: int = 1
    page_size: int = 20


class TraceResult(BaseModel):
    trace_key: str  # Usually lot_no_norm
    p1_found: bool
    p2_count: int
    p3_count: int


class AdvancedSearchResponse(BaseModel):
    total: int
    results: list[TraceResult]


class TraceDetailResponse(BaseModel):
    trace_key: str
    p1: dict[str, Any] | None
    p2: list[dict[str, Any]]
    p3: list[dict[str, Any]]


class DynamicFilter(BaseModel):
    """A safe, allowlisted dynamic filter that can be translated to v2 advanced query params."""

    field: str = Field(..., description="Allowlisted field key")
    op: str = Field(..., description="Allowlisted operator")
    value: Any = Field(
        None, description="Operator value; may be scalar or list depending on op"
    )


class DynamicQueryRequest(BaseModel):
    """Dynamic query request.

    This endpoint intentionally supports only a constrained subset of fields/operators
    and translates them to the existing strict v2 advanced query implementation.
    """

    data_type: str | None = Field(None, description="P1|P2|P3")
    filters: list[DynamicFilter] = Field(default_factory=list)
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)


def _validate_row_data_key(raw_key: str) -> str:
    key = (raw_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="row_data key is required")
    if len(key) > 80:
        raise HTTPException(status_code=400, detail="row_data key is too long")
    # Keep the syntax unambiguous: row_data.<key> only.
    if "." in key:
        raise HTTPException(status_code=400, detail="row_data key cannot contain '.'")
    # Disallow ASCII control characters.
    if any(ord(ch) < 32 for ch in key):
        raise HTTPException(
            status_code=400, detail="row_data key contains invalid characters"
        )
    return key


def _coerce_row_data_terms(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for v in value:
            s = str(v).strip() if v is not None else ""
            if s:
                out.append(s)
        return out
    s = str(value).strip()
    return [s] if s else []


def _row_data_key_aliases(raw_key: str) -> list[str]:
    base = (raw_key or "").strip()
    if not base:
        return []

    normalized = re.sub(r"\s+", " ", base).strip()
    aliases: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        value = re.sub(r"\s+", " ", (candidate or "").strip()).strip()
        if not value or value in seen:
            return
        aliases.append(value)
        seen.add(value)

    add(normalized)

    if normalized.replace(" ", "").lower() in {"stripedresults", "stripedresult"}:
        add("Striped Results")
        add("Striped results")
        add("striped results")
        add("striped result")
        add("分條結果")

    return aliases


def _row_data_value_matches(raw_value: Any, op: str, value: Any) -> bool:
    if raw_value is None:
        return False

    v_norm = normalize_search_term(raw_value) or ""
    if op == "contains":
        term_norm = normalize_search_term(value)
        return bool(term_norm) and term_norm in v_norm
    if op == "eq":
        term_norm = normalize_search_term(value)
        return bool(term_norm) and v_norm == term_norm
    if op == "all_of":
        terms = _coerce_row_data_terms(value)
        norms = [normalize_search_term(t) for t in terms]
        norms = [n for n in norms if n]
        return bool(norms) and all(n in v_norm for n in norms)
    return False


# --- Legacy-compatible schemas (for frontend QueryPage) ---


class QueryRecordV2Compat(BaseModel):
    id: str
    lot_no: str
    data_type: str  # 'P1' | 'P2' | 'P3'
    production_date: str | None = None
    created_at: str
    display_name: str

    # Optional known fields used by frontend (kept for compatibility)
    winder_number: int | None = None
    # For merged P2 cards: list of winders that match advanced filters.
    winder_numbers: list[int] | None = None
    product_id: str | None = None
    machine_no: str | None = None
    mold_no: str | None = None
    source_winder: int | None = None
    specification: str | None = None
    additional_data: dict[str, Any] | None = None


class QueryResponseV2Compat(BaseModel):
    total_count: int
    page: int
    page_size: int
    records: list[QueryRecordV2Compat]


class LotGroupV2Compat(BaseModel):
    lot_no: str
    p1_count: int
    p2_count: int
    p3_count: int
    total_count: int
    latest_production_date: str | None = None
    created_at: str


class LotGroupListV2Compat(BaseModel):
    total_count: int
    page: int
    page_size: int
    groups: list[LotGroupV2Compat]


class RecordStatsV2Compat(BaseModel):
    total_records: int
    unique_lots: int
    p1_records: int
    p2_records: int
    p3_records: int
    latest_production_date: str | None
    earliest_production_date: str | None


def _yyyymmdd_to_yyyy_mm_dd(v: int | None) -> str | None:
    if not v:
        return None
    s = str(v)
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def _max_isoformat(values: Iterable[Any | None]) -> str | None:
    best = None
    for v in values:
        if v is None:
            continue
        if best is None or v > best:
            best = v
    return best.isoformat() if best is not None else None


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


def _first_row(extras: Any) -> dict[str, Any] | None:
    if not isinstance(extras, dict):
        return None
    rows = extras.get("rows")
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    return first if isinstance(first, dict) else None


def _extract_spec_from_row(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    for key in [
        "specification",
        "Specification",
        "SPECIFICATION",
        "規格",
        "產品規格",
        "P3規格",
        "Spec",
        "spec",
    ]:
        v = row.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _normalize_production_date(value: Any) -> str | None:
    if value is None:
        return None

    # Handle numeric-ish values like 250717 or 250717.0
    try:
        if isinstance(value, (int, float)):
            value = str(int(value))
    except Exception:
        pass

    s = str(value).strip()
    if not s:
        return None

    # Common CSV artifact: "250717.0" (float rendered as string)
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]

    # Common merged-data shape: YYYYMMDD_16_00
    if "_" in s:
        s = s.split("_", 1)[0]

    # Normalize separators
    if "/" in s and "-" not in s:
        s = s.replace("/", "-")

    # Already ISO-ish
    parts = s.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        try:
            y = int(parts[0])
            m = int(parts[1])
            d = int(parts[2])
            if 1 <= m <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100:
                return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            pass

    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 8:
        try:
            y = int(digits[:4])
            m = int(digits[4:6])
            d = int(digits[6:8])
            if 1 <= m <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100:
                return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            pass

    if len(digits) == 6:
        # Assume 20YYMMDD (matches UT dataset)
        try:
            yy = int(digits[:2])
            m = int(digits[2:4])
            d = int(digits[4:6])
            y = 2000 + yy
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            pass

    return s


def _extract_production_date_from_row(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    for key in [
        "production_date",
        "Production Date",
        "Production date",
        "Production Date_x",
        "Production Date_y",
        "Slitting date",
        "year-month-day",
        "Year-Month-Day",
        "生產日期",
        "日期",
    ]:
        v = row.get(key)
        if v is None:
            continue
        normalized = _normalize_production_date(v)
        if normalized:
            return normalized
    return None


def _to_yyyymmdd_from_record_production_date(value: Any) -> int | None:
    normalized = _normalize_production_date(value)
    if not normalized:
        return None
    try:
        return int(date.fromisoformat(normalized).strftime("%Y%m%d"))
    except Exception:
        return None


def _filter_records_by_production_date_range(
    records: list["QueryRecordV2Compat"],
    date_from_i: int | None,
    date_to_i: int | None,
) -> list["QueryRecordV2Compat"]:
    # Apply the same date-range semantics to P1/P2/P3:
    # - when date filter exists, records with missing/unparseable production_date are excluded
    if date_from_i is None and date_to_i is None:
        return records

    filtered: list[QueryRecordV2Compat] = []
    for rec in records:
        rec_date_i = _to_yyyymmdd_from_record_production_date(rec.production_date)
        if rec_date_i is None:
            continue
        if date_from_i is not None and rec_date_i < date_from_i:
            continue
        if date_to_i is not None and rec_date_i > date_to_i:
            continue
        filtered.append(rec)
    return filtered


def _extract_p2_item_date_yyyymmdd(item: Any) -> int | None:
    # Prefer structured column populated at import time.
    try:
        ymd = getattr(item, "production_date_yyyymmdd", None)
        if ymd is not None:
            ymd_i = int(ymd)
            if ymd_i > 0:
                return ymd_i
    except Exception:
        pass

    # Backward compatibility for legacy rows before structured date backfill.
    raw = item.row_data if isinstance(getattr(item, "row_data", None), dict) else None
    if not raw:
        return None
    row = dict(raw)
    nested = raw.get("rows")
    if isinstance(nested, list) and nested and isinstance(nested[0], dict):
        row.update(nested[0])
    return _to_yyyymmdd_from_record_production_date(_extract_production_date_from_row(row))


def _extract_p2_item_slitting_result(item: Any) -> float | None:
    # 優先使用已結構化欄位，否則回退到 row_data（含 aliases 與 rows[0]）做相容。
    raw = item.row_data if isinstance(getattr(item, "row_data", None), dict) else {}
    if not raw and not isinstance(raw, dict):
        raw = {}

    if getattr(item, "slitting_result", None) is not None:
        try:
            return float(item.slitting_result)
        except (TypeError, ValueError):
            pass

    row: dict[str, Any] = dict(raw)
    nested = raw.get("rows")
    if isinstance(nested, list) and nested and isinstance(nested[0], dict):
        row.update(nested[0])

    aliases = [
        "Striped Results",
        "Striped results",
        "striped results",
        "striped result",
        "Slitting Result",
        "slitting result",
        "slitting_result",
        "分條結果",
        "分條結果(成品)",
    ]
    for alias in aliases:
        if alias not in row:
            continue
        try:
            return float(row[alias])
        except (TypeError, ValueError):
            continue

    return None


def _derive_machine_mold(
    record_machine: str | None, record_mold: str | None, extras: dict[str, Any]
) -> tuple[str | None, str | None]:
    machine = None
    mold = None
    if (
        record_machine
        and str(record_machine).strip()
        and str(record_machine).upper() != "UNKNOWN"
    ):
        machine = str(record_machine).strip()
    if (
        record_mold
        and str(record_mold).strip()
        and str(record_mold).upper() != "UNKNOWN"
    ):
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
        data_type="P1",
        production_date=_extract_production_date_from_row(row0),
        created_at=r.created_at.isoformat(),
        display_name=display,
        additional_data=(
            r.extras if isinstance(r.extras, dict) else {}
        ),  # 修復: 返回完整 extras 而非只有 row0
    )


def _p2_to_query_record_with_items(
    p2_record: P2Record, items: list
) -> QueryRecordV2Compat:
    """
    組合 P2Record + P2ItemsV2 為查詢結果
    items: List[P2ItemV2]
    """
    # 將 items 轉為 rows 格式（前端期望）
    rows = []
    for item in items:
        raw = item.row_data if isinstance(item.row_data, dict) else {}
        # Some datasets store the real row fields inside row_data.rows[0]
        # (legacy import shape). Flatten it to keep UI tables consistent.
        row: dict = {}
        if (
            isinstance(raw.get("rows"), list)
            and raw.get("rows")
            and isinstance(raw.get("rows")[0], dict)
        ):
            row.update({k: v for k, v in raw.items() if k != "rows"})
            row.update(raw.get("rows")[0])
        else:
            row.update(raw)
        row["winder_number"] = item.winder_number
        # 加入結構化欄位
        for field in [
            "sheet_width",
            "thickness1",
            "thickness2",
            "thickness3",
            "thickness4",
            "thickness5",
            "thickness6",
            "thickness7",
            "appearance",
            "rough_edge",
            "slitting_result",
        ]:
            val = getattr(item, field, None)
            if val is not None:
                row[field] = val
        rows.append(row)

    # 按 winder_number 排序
    rows.sort(key=lambda x: x.get("winder_number", 0))

    winder_numbers = sorted(
        {
            int(r.get("winder_number"))
            for r in rows
            if isinstance(r.get("winder_number"), (int, float))
        }
    )

    # 優先從已扁平化 rows 抽取日期，確保支援 row_data.rows[0] 形態。
    production_date = _extract_production_date_from_row(
        rows[0] if rows and isinstance(rows[0], dict) else None
    )

    # 相容舊資料：若 rows 仍無日期，再回頭看第一個 item 的原始 row_data。
    if not production_date:
        first_item = items[0] if items else None
        if first_item and isinstance(first_item.row_data, dict):
            production_date = _extract_production_date_from_row(first_item.row_data)
        if not production_date and first_item is not None:
            ymd = _extract_p2_item_date_yyyymmdd(first_item)
            if ymd:
                production_date = _yyyymmdd_to_yyyy_mm_dd(int(ymd))

    return QueryRecordV2Compat(
        id=str(p2_record.id),
        lot_no=p2_record.lot_no_raw,
        data_type="P2",
        production_date=production_date,
        created_at=p2_record.created_at.isoformat(),
        display_name=p2_record.lot_no_raw,
        winder_number=None,  # 合併模式
        winder_numbers=winder_numbers or None,
        additional_data={"rows": rows},
    )


def _p2_to_query_record(r: P2Record) -> QueryRecordV2Compat:
    """Legacy fallback - 當沒有 items 時使用"""
    display = f"{r.lot_no_raw} (W{r.winder_number})"
    row0 = _first_row(r.extras)
    return QueryRecordV2Compat(
        id=str(r.id),
        lot_no=r.lot_no_raw,
        data_type="P2",
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
            if isinstance(rec.extras, dict):
                extras = rec.extras
                row: dict = {}
                # Legacy shape: extras may be { rows: [ { ...real fields... } ], ... }
                if (
                    isinstance(extras.get("rows"), list)
                    and extras.get("rows")
                    and isinstance(extras.get("rows")[0], dict)
                ):
                    row.update({k: v for k, v in extras.items() if k != "rows"})
                    row.update(extras.get("rows")[0])
                else:
                    row.update(extras)
                # 確保 winder_number 包含在 row 中（前端可能需要）
                row["winder_number"] = rec.winder_number
                rows.append(row)

        # 組裝 additional_data (包含 rows 陣列)
        merged_extras = {
            "lot_no": first.lot_no_raw,
            "rows": rows,  # 前端期望此欄位名稱
        }

        # 從第一個 winder 的 extras 提取共同資訊（保留共同欄位）
        if isinstance(first.extras, dict):
            for key in [
                "format",
                "Format",
                "規格",
                "production_date",
                "Production Date",
                "生產日期",
            ]:
                if key in first.extras:
                    merged_extras[key] = first.extras[key]

        merged_results.append(
            QueryRecordV2Compat(
                id=str(first.id),  # 使用第一個 winder 的 ID
                lot_no=first.lot_no_raw,
                data_type="P2",
                production_date=_extract_production_date_from_row(row0),
                created_at=first.created_at.isoformat(),
                display_name=first.lot_no_raw,  # 不再顯示 winder number
                winder_number=None,  # 合併後不顯示單一 winder
                additional_data=merged_extras,
            )
        )

    return merged_results


def _p3_to_query_record_with_items(
    p3_record: P3Record, items: list
) -> QueryRecordV2Compat:
    """
    組合 P3Record + P3ItemsV2 為查詢結果
    items: List[P3ItemV2]
    """
    # 將 items 轉為 rows 格式
    rows = []
    for item in items:
        row = dict(item.row_data) if isinstance(item.row_data, dict) else {}
        row["row_no"] = item.row_no
        # Keep row-level product_id semantics: never force record-level fallback here.
        # Frontend can derive display id if this value is missing.
        if item.product_id:
            row["product_id"] = item.product_id
        else:
            row.pop("product_id", None)
        row["source_winder"] = item.source_winder
        row["specification"] = item.specification
        rows.append(row)

    # 按 row_no 排序
    rows.sort(key=lambda x: x.get("row_no", 0))

    return QueryRecordV2Compat(
        id=str(p3_record.id),
        lot_no=p3_record.lot_no_raw,
        data_type="P3",
        production_date=_yyyymmdd_to_yyyy_mm_dd(p3_record.production_date_yyyymmdd),
        created_at=p3_record.created_at.isoformat(),
        display_name=p3_record.product_id or p3_record.lot_no_raw,
        product_id=p3_record.product_id,
        machine_no=p3_record.machine_no,
        mold_no=p3_record.mold_no,
        specification=items[0].specification if items else None,
        additional_data={"rows": rows},
    )


def _p3_to_query_record(r: P3Record) -> QueryRecordV2Compat:
    """Legacy fallback - 當沒有 items 時使用"""
    machine, mold = _derive_machine_mold(r.machine_no, r.mold_no, r.extras)
    display = r.product_id or r.lot_no_raw
    row0 = _first_row(r.extras)
    return QueryRecordV2Compat(
        id=str(r.id),
        lot_no=r.lot_no_raw,
        data_type="P3",
        production_date=_yyyymmdd_to_yyyy_mm_dd(r.production_date_yyyymmdd),
        created_at=r.created_at.isoformat(),
        display_name=display,
        product_id=r.product_id,
        machine_no=machine,
        mold_no=mold,
        specification=_extract_spec_from_row(row0),
        additional_data=(r.extras if isinstance(r.extras, dict) else None),
    )


def _derive_machine_mold_from_extras(
    extras: dict[str, Any],
) -> tuple[str | None, str | None]:
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
