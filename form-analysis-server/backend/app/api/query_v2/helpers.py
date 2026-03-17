import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any

from fastapi import HTTPException

from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.utils.normalization import normalize_search_term

from .schemas import QueryRecordV2Compat


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
