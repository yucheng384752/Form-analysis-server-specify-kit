"""
Analytics Data Fetcher

從資料庫撈取 P1、P2、P3 資料，組合為符合 merged_p1_p2_p3.csv 格式的 DataFrame，
供分析模組使用。解決直方圖顯示時資料來源與 NG 查詢資料來源不一致的問題。
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pandas as pd
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ==============================================================================
# Date Parsing Helpers
# ==============================================================================


def parse_p2_slitting_date_to_yyyymmdd(raw: str | None) -> int | None:
    """
    解析 P2 分條時間欄位為 YYYYMMDD 整數。

    支援格式：
    - 20250807_16_00 (YYYYMMDD 開頭)
    - 114年8月20日11:00 (民國年格式)
    - 2025-08-07 (ISO 格式)
    - 20250807 (純數字)

    Args:
        raw: 原始分條時間字串

    Returns:
        YYYYMMDD 整數；無效格式返回 None
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = str(raw).strip()

    # Pattern 1: YYYYMMDD 開頭，後面可能有 _HH_MM 或其他後綴
    match = re.match(r"^(\d{8})(?:_|$)", raw)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    # Pattern 2: 民國年格式 - YYY年M月D日 (可能有時間後綴)
    # 例如：114年8月20日11:00 或 114年09月02日
    match = re.match(r"^(\d{2,3})年(\d{1,2})月(\d{1,2})日", raw)
    if match:
        try:
            roc_year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            western_year = roc_year + 1911
            return western_year * 10000 + month * 100 + day
        except ValueError:
            pass

    # Pattern 3: ISO 格式 YYYY-MM-DD
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return year * 10000 + month * 100 + day
        except ValueError:
            pass

    # Pattern 4: 純 8 位數字
    if re.match(r"^\d{8}$", raw):
        try:
            return int(raw)
        except ValueError:
            pass

    return None


def parse_p3_year_month_day_to_yyyymmdd(raw: str | None) -> int | None:
    """
    解析 P3 year-month-day 欄位 (格式: 114年09月02日) 為 YYYYMMDD 整數。

    Args:
        raw: 原始日期字串，如 "114年09月02日"

    Returns:
        YYYYMMDD 整數，如 20250902；無效格式返回 None
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = str(raw).strip()

    # Pattern: YYY年MM月DD日 (民國年)
    match = re.match(r"^(\d{2,3})年(\d{1,2})月(\d{1,2})日$", raw)
    if match:
        try:
            roc_year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            western_year = roc_year + 1911
            return western_year * 10000 + month * 100 + day
        except ValueError:
            pass

    # 也支援西元年格式: YYYY年MM月DD日
    match = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$", raw)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return year * 10000 + month * 100 + day
        except ValueError:
            pass

    # 也支援 YYYYMMDD 格式
    if re.match(r"^\d{8}$", raw):
        try:
            return int(raw)
        except ValueError:
            pass

    # 也支援 YYYY-MM-DD 格式
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", raw)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return year * 10000 + month * 100 + day
        except ValueError:
            pass

    return None


def yyyymmdd_to_date(yyyymmdd: int | None) -> date | None:
    """將 YYYYMMDD 整數轉換為 date 物件"""
    if yyyymmdd is None:
        return None
    try:
        year = yyyymmdd // 10000
        month = (yyyymmdd % 10000) // 100
        day = yyyymmdd % 100
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def is_date_in_range(
    yyyymmdd: int | None,
    start_yyyymmdd: int | None,
    end_yyyymmdd: int | None,
) -> bool:
    """
    檢查日期是否在指定範圍內。

    Args:
        yyyymmdd: 要檢查的日期 (YYYYMMDD)
        start_yyyymmdd: 開始日期 (YYYYMMDD)，None 表示無下限
        end_yyyymmdd: 結束日期 (YYYYMMDD)，None 表示無上限

    Returns:
        True 如果日期在範圍內
    """
    if yyyymmdd is None:
        return False

    if start_yyyymmdd is not None and yyyymmdd < start_yyyymmdd:
        return False

    if end_yyyymmdd is not None and yyyymmdd > end_yyyymmdd:
        return False

    return True


def parse_date_string_to_yyyymmdd(date_str: str | None) -> int | None:
    """
    解析日期字串 (YYYY-MM-DD 或 YYYYMMDD) 為 YYYYMMDD 整數。

    Args:
        date_str: 日期字串，如 "2025-08-01" 或 "20250801"

    Returns:
        YYYYMMDD 整數
    """
    if not date_str:
        return None

    date_str = str(date_str).strip()

    # YYYY-MM-DD format
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_str)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return year * 10000 + month * 100 + day
        except ValueError:
            pass

    # YYYYMMDD format
    if re.match(r"^\d{8}$", date_str):
        try:
            return int(date_str)
        except ValueError:
            pass

    # YYYY-MM format (assume first day of month for start, last day for end)
    match = re.match(r"^(\d{4})-(\d{2})$", date_str)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            return year * 10000 + month * 100 + 1  # Default to first day
        except ValueError:
            pass

    return None


# ==============================================================================
# Field Extraction Helpers
# ==============================================================================


# P2 分條時間欄位的可能名稱
P2_SLITTING_DATE_FIELD_NAMES = [
    "分條時間",
    "Slitting date",
    "Slitting Date",
    "slitting_date",
    "Slitting Time",
    "slitting time",
]

# P3 年月日欄位的可能名稱
P3_YEAR_MONTH_DAY_FIELD_NAMES = [
    "year-month-day",
    "Year-Month-Day",
    "year_month_day",
    "production_date",
    "Production Date",
    "生產日期",
]


def extract_p2_slitting_date(row_data: dict[str, Any]) -> str | None:
    """從 P2 row_data 提取分條時間欄位值"""
    if not row_data:
        return None
    for field in P2_SLITTING_DATE_FIELD_NAMES:
        if field in row_data and row_data[field]:
            return str(row_data[field])
    return None


def extract_p3_year_month_day(row_data: dict[str, Any]) -> str | None:
    """從 P3 row_data 提取 year-month-day 欄位值"""
    if not row_data:
        return None
    for field in P3_YEAR_MONTH_DAY_FIELD_NAMES:
        if field in row_data and row_data[field]:
            return str(row_data[field])
    return None


# ==============================================================================
# Main Data Fetch Function
# ==============================================================================


async def fetch_merged_p1p2p3_from_db(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    stations: list[str] | None = None,
) -> pd.DataFrame:
    """
    從資料庫撈取 P1、P2、P3 資料，組合為符合 merged_p1_p2_p3.csv 格式的 DataFrame。

    資料流程：
    1. 根據 stations 決定要撈取哪些表格
    2. P2 使用「分條時間」欄位做日期過濾
    3. P3 使用「year-month-day」欄位做日期過濾
    4. 以 P2 為主表，LEFT JOIN P1 和 P3（透過 lot_no_norm 關聯）

    Args:
        db: AsyncSession
        tenant_id: 租戶 ID
        start_date: 開始日期 (YYYY-MM-DD)，None 表示無下限
        end_date: 結束日期 (YYYY-MM-DD)，None 表示無上限
        stations: 站點列表 ["P2", "P3", "ALL"]，None 等同 ["ALL"]

    Returns:
        pd.DataFrame: 符合 merged_p1_p2_p3.csv 格式的 DataFrame
    """
    from app.models.p1_record import P1Record
    from app.models.p2_item_v2 import P2ItemV2
    from app.models.p2_record import P2Record
    from app.models.p3_item_v2 import P3ItemV2
    from app.models.p3_record import P3Record

    # Normalize stations
    if stations is None:
        stations = ["ALL"]
    stations_upper = [s.upper() for s in stations]
    include_p2 = "ALL" in stations_upper or "P2" in stations_upper
    include_p3 = "ALL" in stations_upper or "P3" in stations_upper

    # Parse date range
    start_yyyymmdd = parse_date_string_to_yyyymmdd(start_date)
    end_yyyymmdd = parse_date_string_to_yyyymmdd(end_date)

    # If end_date is YYYY-MM format, set to last day of month
    if end_date and re.match(r"^\d{4}-\d{2}$", end_date):
        year = int(end_date[:4])
        month = int(end_date[5:7])
        if month == 12:
            end_yyyymmdd = (year + 1) * 10000 + 1 * 100 + 1 - 1  # Dec 31
        else:
            # Last day of month = first day of next month - 1
            end_yyyymmdd = year * 10000 + (month + 1) * 100 + 1 - 1

    logger.info(
        "Fetching merged P1/P2/P3 data from DB: tenant=%s, range=%s~%s, stations=%s",
        tenant_id,
        start_yyyymmdd,
        end_yyyymmdd,
        stations,
    )

    rows: list[dict[str, Any]] = []

    # Build lot_no_norm -> P1 data mapping
    p1_by_lot_norm: dict[int, dict[str, Any]] = {}

    stmt_p1 = select(P1Record).where(P1Record.tenant_id == tenant_id)
    result_p1 = await db.execute(stmt_p1)
    p1_records = result_p1.scalars().all()

    for p1 in p1_records:
        if p1.extras and "rows" in p1.extras and p1.extras["rows"]:
            p1_row = p1.extras["rows"][0] if p1.extras["rows"] else {}
            p1_by_lot_norm[p1.lot_no_norm] = {
                "lot_no_raw": p1.lot_no_raw,
                "lot_no_norm": p1.lot_no_norm,
                "row_data": p1_row,
            }

    # Fetch P2 items with date filtering
    if include_p2:
        stmt_p2 = (
            select(P2ItemV2)
            .join(P2Record, P2ItemV2.p2_record_id == P2Record.id)
            .where(P2ItemV2.tenant_id == tenant_id)
            .options(selectinload(P2ItemV2.p2_record))
        )
        # SQL-level date pre-filter using indexed production_date_yyyymmdd
        if start_yyyymmdd is not None:
            stmt_p2 = stmt_p2.where(
                or_(
                    P2ItemV2.production_date_yyyymmdd >= start_yyyymmdd,
                    P2ItemV2.production_date_yyyymmdd.is_(None),
                )
            )
        if end_yyyymmdd is not None:
            stmt_p2 = stmt_p2.where(
                or_(
                    P2ItemV2.production_date_yyyymmdd <= end_yyyymmdd,
                    P2ItemV2.production_date_yyyymmdd.is_(None),
                )
            )
        result_p2 = await db.execute(stmt_p2)
        p2_items = result_p2.scalars().all()

        for p2_item in p2_items:
            row_data = p2_item.row_data or {}

            # Use production_date_yyyymmdd directly (semantically equivalent to Slitting date)
            slitting_yyyymmdd = p2_item.production_date_yyyymmdd

            # Apply date filter
            # If slitting_yyyymmdd is None, let the row through:
            # the SQL pre-filter already passed None-dated rows intentionally.
            if start_yyyymmdd is not None or end_yyyymmdd is not None:
                if slitting_yyyymmdd is not None and not is_date_in_range(
                    slitting_yyyymmdd, start_yyyymmdd, end_yyyymmdd
                ):
                    continue

            # Get P1 data by lot_no_norm
            lot_no_norm = p2_item.p2_record.lot_no_norm if p2_item.p2_record else None
            p1_data = p1_by_lot_norm.get(lot_no_norm, {}) if lot_no_norm else {}
            p1_row = p1_data.get("row_data", {})

            # Build merged row
            merged_row = _build_merged_row(
                p1_row=p1_row,
                p2_row=row_data,
                p3_row={},
                lot_no_raw=p2_item.p2_record.lot_no_raw if p2_item.p2_record else None,
            )
            # Fallback: ensure Winder number from structured field
            if (
                merged_row.get("Winder number") is None
                and p2_item.winder_number is not None
            ):
                merged_row["Winder number"] = p2_item.winder_number
            # Fallback: populate Slitting date from structured field
            # so that _filter_df second-pass date filtering works correctly
            if (
                merged_row.get("Slitting date") is None
                and p2_item.production_date_yyyymmdd is not None
            ):
                merged_row["Slitting date"] = str(p2_item.production_date_yyyymmdd)
            rows.append(merged_row)

    # Fetch P3 items with date filtering (if P3 is selected)
    if include_p3:
        stmt_p3 = (
            select(P3ItemV2)
            .join(P3Record, P3ItemV2.p3_record_id == P3Record.id)
            .where(P3ItemV2.tenant_id == tenant_id)
            .options(selectinload(P3ItemV2.p3_record))
        )
        # SQL-level date pre-filter using P3ItemV2.production_date
        if start_yyyymmdd is not None:
            start_dt = yyyymmdd_to_date(start_yyyymmdd)
            if start_dt is not None:
                stmt_p3 = stmt_p3.where(
                    or_(
                        P3ItemV2.production_date >= start_dt,
                        P3ItemV2.production_date.is_(None),
                    )
                )
        if end_yyyymmdd is not None:
            end_dt = yyyymmdd_to_date(end_yyyymmdd)
            if end_dt is not None:
                stmt_p3 = stmt_p3.where(
                    or_(
                        P3ItemV2.production_date <= end_dt,
                        P3ItemV2.production_date.is_(None),
                    )
                )
        result_p3 = await db.execute(stmt_p3)
        p3_items = result_p3.scalars().all()
        logger.info(
            "[DEBUG] fetch_merged: SQL returned %d P3 rows (date range %s~%s)",
            len(p3_items),
            start_yyyymmdd,
            end_yyyymmdd,
        )

        for p3_item in p3_items:
            row_data = p3_item.row_data or {}

            # Use production_date directly (semantically equivalent to year-month-day in row_data)
            p3_yyyymmdd = None
            if p3_item.production_date is not None:
                d = p3_item.production_date
                p3_yyyymmdd = d.year * 10000 + d.month * 100 + d.day

            # Apply date filter
            # If p3_yyyymmdd is None, let the row through:
            # the SQL pre-filter already passed None-dated rows intentionally.
            if start_yyyymmdd is not None or end_yyyymmdd is not None:
                if p3_yyyymmdd is not None and not is_date_in_range(
                    p3_yyyymmdd, start_yyyymmdd, end_yyyymmdd
                ):
                    continue

            # Get P1 data by lot_no_norm
            lot_no_norm = p3_item.p3_record.lot_no_norm if p3_item.p3_record else None
            p1_data = p1_by_lot_norm.get(lot_no_norm, {}) if lot_no_norm else {}
            p1_row = p1_data.get("row_data", {})

            # Build merged row (P3 only, no P2)
            merged_row = _build_merged_row(
                p1_row=p1_row,
                p2_row={},
                p3_row=row_data,
                lot_no_raw=p3_item.p3_record.lot_no_raw if p3_item.p3_record else None,
            )
            # Fallback: populate Production Date_x from structured field
            # so that _filter_df second-pass date filtering works correctly
            if (
                merged_row.get("Production Date_x") is None
                and p3_item.production_date is not None
            ):
                d = p3_item.production_date
                merged_row["Production Date_x"] = f"{d.year}{d.month:02d}{d.day:02d}"
            if (
                merged_row.get("Production Date_y") is None
                and p3_item.production_date is not None
            ):
                d = p3_item.production_date
                merged_row["Production Date_y"] = f"{d.year}{d.month:02d}{d.day:02d}"
            rows.append(merged_row)

    logger.info("Fetched %d merged rows from DB", len(rows))

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


# ==============================================================================
# Fetch Merged Data by Product IDs (客訴追溯)
# ==============================================================================


async def fetch_merged_by_product_ids(
    db: AsyncSession,
    tenant_id: UUID,
    product_ids: list[str],
) -> pd.DataFrame:
    """
    根據客訴 product_id 列表追溯 P1/P2/P3 資料，組合為 merged_p1_p2_p3.csv 格式。

    這是客訴分析的關鍵函式：
    1. 將客訴 product_id 轉換為 DB 格式
    2. 透過 P3 -> P2 -> P1 追溯完整生產鏈
    3. 組合成符合 Analytical-Four 期望的 merged 格式

    Args:
        db: AsyncSession
        tenant_id: 租戶 ID
        product_ids: 客訴 product_id 列表 (如 ['250909-P23-2384-301', ...])

    Returns:
        pd.DataFrame: 符合 merged_p1_p2_p3.csv 格式的 DataFrame
    """
    from app.models.p1_record import P1Record
    from app.models.p2_item_v2 import P2ItemV2
    from app.models.p2_record import P2Record
    from app.models.p3_item_v2 import P3ItemV2
    from app.models.p3_record import P3Record
    from app.utils.normalization import normalize_lot_no

    if not product_ids:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []

    # Build P1 lookup by lot_no_norm
    p1_by_lot_norm: dict[int, dict[str, Any]] = {}
    stmt_p1 = select(P1Record).where(P1Record.tenant_id == tenant_id)
    result_p1 = await db.execute(stmt_p1)
    p1_records = result_p1.scalars().all()

    for p1 in p1_records:
        if p1.extras and "rows" in p1.extras and p1.extras["rows"]:
            p1_row = p1.extras["rows"][0] if p1.extras["rows"] else {}
            p1_by_lot_norm[p1.lot_no_norm] = {
                "lot_no_raw": p1.lot_no_raw,
                "lot_no_norm": p1.lot_no_norm,
                "row_data": p1_row,
            }

    for raw_pid in product_ids:
        pid = _normalize_product_id(raw_pid)
        if not pid:
            logger.warning("Invalid product_id format: %s", raw_pid)
            continue

        # Step 1: Find P3 by product_id
        p3_item_stmt = (
            select(P3ItemV2)
            .options(selectinload(P3ItemV2.p3_record))
            .where(
                P3ItemV2.tenant_id == tenant_id,
                P3ItemV2.product_id == pid,
            )
        )
        p3_result = await db.execute(p3_item_stmt)
        p3_item = p3_result.scalar_one_or_none()

        p3_row: dict[str, Any] = {}
        p2_row: dict[str, Any] = {}
        p1_row: dict[str, Any] = {}
        lot_no_raw: str | None = None
        lot_no_norm: int | None = None
        source_winder: int | None = None
        p2_item = None

        if p3_item:
            p3_row = p3_item.row_data or {}
            lot_no_raw = p3_item.lot_no
            source_winder = p3_item.source_winder

            # Prefer P3 record normalized lot_no to avoid suffix mismatch.
            if p3_item.p3_record:
                lot_no_norm = p3_item.p3_record.lot_no_norm
                if not lot_no_raw:
                    lot_no_raw = p3_item.p3_record.lot_no_raw

            # Fallback: normalize lot_no from P3 item if record is missing.
            if lot_no_norm is None and lot_no_raw:
                try:
                    lot_no_norm = normalize_lot_no(lot_no_raw)
                except Exception:
                    lot_no_norm = None
        else:
            # Try P3Record fallback
            p3_record_stmt = (
                select(P3Record)
                .options(selectinload(P3Record.items_v2))
                .where(
                    P3Record.tenant_id == tenant_id,
                    P3Record.product_id == pid,
                )
            )
            p3_record_result = await db.execute(p3_record_stmt)
            p3_record = p3_record_result.scalar_one_or_none()

            if p3_record and p3_record.items_v2:
                p3_item = p3_record.items_v2[0]
                p3_row = p3_item.row_data or {}
                lot_no_raw = p3_record.lot_no_raw
                lot_no_norm = p3_record.lot_no_norm
                source_winder = p3_item.source_winder

        # Step 2: Find P2 by lot_no_norm and winder
        # If source_winder wasn't stored on the P3 item, try to derive it from
        # the P3 lot_no format "YYYYDDD_MM_WW" (e.g. "2507173_02_17" → 17).
        if source_winder is None and lot_no_raw:
            parts = str(lot_no_raw).strip().split("_")
            if len(parts) >= 3:
                try:
                    source_winder = int(parts[2])
                except (ValueError, TypeError):
                    pass

        if lot_no_norm is not None:
            p2_stmt = (
                select(P2ItemV2)
                .join(P2Record, P2ItemV2.p2_record_id == P2Record.id)
                .options(selectinload(P2ItemV2.p2_record))
                .where(
                    P2ItemV2.tenant_id == tenant_id,
                    P2Record.lot_no_norm == lot_no_norm,
                )
            )
            if source_winder is not None:
                p2_stmt = p2_stmt.where(P2ItemV2.winder_number == source_winder)
            else:
                p2_stmt = p2_stmt.order_by(P2ItemV2.winder_number)

            p2_result = await db.execute(p2_stmt)
            p2_item = p2_result.scalars().first()

            if p2_item:
                p2_row = p2_item.row_data or {}

        # Step 3: Find P1 by lot_no_norm
        if lot_no_norm is not None:
            p1_data = p1_by_lot_norm.get(lot_no_norm, {})
            p1_row = p1_data.get("row_data", {})
            if not lot_no_raw:
                lot_no_raw = p1_data.get("lot_no_raw")

        # Build merged row
        if p3_row or p2_row or p1_row:
            merged_row = _build_merged_row(
                p1_row=p1_row,
                p2_row=p2_row,
                p3_row=p3_row,
                lot_no_raw=lot_no_raw,
            )
            # Fallback: ensure Winder number from structured field
            if merged_row.get("Winder number") is None:
                if p2_item is not None and p2_item.winder_number is not None:
                    merged_row["Winder number"] = p2_item.winder_number
                elif source_winder is not None:
                    merged_row["Winder number"] = source_winder
            # Fallback: ensure Striped Results from structured field so
            # CategoricalAnalyzer target-column filter does not drop the row
            if merged_row.get("Striped Results") is None and p2_item is not None and p2_item.slitting_result is not None:
                merged_row["Striped Results"] = p2_item.slitting_result
            # Add original product_id for reference
            merged_row["_original_product_id"] = raw_pid
            merged_row["_normalized_product_id"] = pid
            rows.append(merged_row)
            logger.debug("Traced product_id %s -> lot_no=%s", pid, lot_no_raw)
        else:
            logger.warning("No data found for product_id: %s", pid)

    logger.info(
        "Fetched %d merged rows from %d product_ids", len(rows), len(product_ids)
    )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _normalize_product_id(raw_id: str) -> str | None:
    """
    將客訴格式的 product_id 轉換為 DB 格式

    Examples:
        '250909-P23-2384-301' -> '20250909_P23_238-4_301'
        '20250909_P23_238-4_301' -> '20250909_P23_238-4_301' (已是正確格式)
    """
    raw_id = raw_id.strip()

    # Already in correct format
    if re.match(r"^\d{8}_[A-Z]\d{2}_\d{3}-\d_\d+$", raw_id):
        return raw_id

    # Convert from complaint format: YYMMDD-PXX-XXXN-NNN
    m = re.match(r"^(\d{6})-([A-Z]\d{2})-(\d{3})(\d)-(\d+)$", raw_id)
    if m:
        date_str, prod, mat1, mat2, seq = m.groups()
        return f"20{date_str}_{prod}_{mat1}-{mat2}_{seq}"

    # Try with full year: YYYYMMDD-PXX-XXXN-NNN
    m = re.match(r"^(\d{8})-([A-Z]\d{2})-(\d{3})(\d)-(\d+)$", raw_id)
    if m:
        date_str, prod, mat1, mat2, seq = m.groups()
        return f"{date_str}_{prod}_{mat1}-{mat2}_{seq}"

    logger.warning("Unknown product_id format: %s", raw_id)
    return raw_id  # Return as-is, let DB query handle it


def _build_merged_row(
    *,
    p1_row: dict[str, Any],
    p2_row: dict[str, Any],
    p3_row: dict[str, Any],
    lot_no_raw: str | None,
) -> dict[str, Any]:
    """
    組合 P1、P2、P3 資料為一筆 merged row，
    欄位名稱符合 merged_p1_p2_p3.csv 格式。

    這個對照表基於實際 CSV 欄位名稱：
    - P1 欄位以原始名稱保留，部分加上 "P1." 前綴
    - P2 欄位以原始名稱保留
    - P3 欄位以原始名稱保留，部分加上 "P3." 前綴
    """
    merged: dict[str, Any] = {}

    # LOT NO. 是主要 key
    merged["LOT NO."] = lot_no_raw or ""

    # === P1 欄位 ===
    # 直接從 p1_row 提取，使用標準化的欄位名稱
    p1_field_mapping = {
        # 機台編號
        "P1.Machine_No.": ["Machine NO", "Machine No", "Machine_No.", "machine_no"],
        # 生產日期
        "Production Date": ["Production Date", "production date", "生產日期"],
        # 規格
        "P1.Specification": ["Specification", "specification", "規格"],
        # 材料
        "P1.Material": ["Material", "material", "材料"],
        # 半成品寬度
        "Semi-finished Sheet Width(mm)": [
            "Semi-finished Sheet Width(mm)",
            "Sheet Width(mm)",
            "sheet_width",
        ],
        # 半成品長度
        "Semi-finished Length(M)": ["Semi-finished Length(M)", "Length(M)", "length"],
        # 重量
        "Weight(Kg)": ["Weight(Kg)", "weight"],
    }

    # 溫度欄位 (C1-C16, A/B/C bucket, Top/Mid/Bottom)
    for i in range(1, 17):
        p1_field_mapping[f"Actual Temp_C{i}"] = [
            f"Actual Temp_C{i}(℃)",
            f"Actual Temp_C{i}",
        ]
        p1_field_mapping[f"Set Temp_C{i}"] = [f"Set Temp_C{i}(℃)", f"Set Temp_C{i}"]

    for bucket in ["A bucket", "B bucket", "C bucket"]:
        p1_field_mapping[f"Actual Temp_{bucket}"] = [
            f"Actual Temp_{bucket}(℃)",
            f"Actual Temp_{bucket}",
        ]
        p1_field_mapping[f"Set Temp_{bucket}"] = [
            f"Set Temp_{bucket}(℃)",
            f"Set Temp_{bucket}",
        ]

    for pos in ["Top", "Mid", "Bottom"]:
        p1_field_mapping[f"Actual Temp_{pos}"] = [
            f"Actual Temp_{pos}(℃)",
            f"Actual Temp_{pos}",
        ]
        p1_field_mapping[f"Set Temp_{pos}"] = [f"Set Temp_{pos}(℃)", f"Set Temp_{pos}"]

    # 其他 P1 製程參數
    p1_field_mapping.update(
        {
            "Line Speed(M/min)": ["Line Speed(M/min)", "Line Speed"],
            "Screw Pressure(psi)": ["Screw Pressure(psi)", "Screw Pressure"],
            "Screw Output(%)": ["Screw Output(%)", "Screw Output"],
            "Left Pad Thickness (mm)": [
                "Left Pad Thickness (mm)",
                "Left Pad Thickness",
            ],
            "Right Pad Thickness (mm)": [
                "Right Pad Thickness (mm)",
                "Right Pad Thickness",
            ],
            "Current(A)": ["Current(A)", "Current"],
            "Extruder Speed (rpm)": [
                "Extruder Speed(rpm)",
                "Extruder Speed (rpm)",
                "Extruder Speed",
            ],
            "Quantitative Pressure(psi)": [
                "Quantitative Pressure(psi)",
                "Quantitative Pressure",
            ],
            "Quantitative Output(%)": ["Quantitative Output(%)", "Quantitative Output"],
            "Frame (cm)": ["Frame (cm)", "Frame"],
            "Filter Pressure(psi)": ["Filter Pressure(psi)", "Filter Pressure"],
            "format": ["format"],
        }
    )

    for target_col, source_cols in p1_field_mapping.items():
        merged[target_col] = _get_first_match(p1_row, source_cols)

    # === P2 欄位 ===
    p2_field_mapping = {
        "P2.Material": ["Material", "material"],
        "Semi-finished No.": [
            "Semi-finished productsLOT NO",
            "Semi-finished No.",
            "lot_no",
        ],
        "Semi_produce No.": ["Semi_produce No.", "Semi-finished productsLOT NO"],
        "Slitting date": ["Slitting date", "分條時間", "slitting_date"],
        "Slitting machine": [
            "Slitting machine",
            "Slitting Machine",
            "slitting_machine",
        ],
        "Semi-finished impedance": ["Semi-finished impedance", "impedance"],
        "Heat gun temperature": ["Heat gun temperature"],
        "Rubber wheel gasket thickness (in)": ["Rubber wheel gasket thickness (in)"],
        "Rubber wheel gasket thickness (out)": ["Rubber wheel gasket thickness (out)"],
        "Rewind torque": ["Rewind torque"],
        "Slitting speed": ["Slitting speed"],
        "Meters completed": ["Meters completed"],
        "Winder number": ["Winder number", "Winder", "winder_number", "winder"],
        "Board Width(mm)": ["Board Width(mm)", "Sheet Width(mm)", "sheet_width"],
        "Thicknessss High(μm)": ["Thicknessss High(μm)", "Thickness High(μm)"],
        "Thicknessss Low(μm)": ["Thicknessss Low(μm)", "Thickness Low(μm)"],
        "Appearance": ["Appearance", "appearance"],
        "rough edge": ["rough edge", "Rough edge", "rough_edge"],
        "Striped Results": [
            "Striped Results",
            "Slitting Result",
            "Striped results",
            "slitting_result",
        ],
        "Thickness diff": ["Thickness diff"],
        "Qaulity inspecrion": [
            "Qaulity inspecrion",
            "Quality inspection",
            "quality_inspection",
        ],
        "Qaulity control": ["Qaulity control", "Quality control", "quality_control"],
    }

    for target_col, source_cols in p2_field_mapping.items():
        merged[target_col] = _get_first_match(p2_row, source_cols)

    # === P3 欄位 ===
    p3_field_mapping = {
        "Production Date_x": ["year-month-day", "Production Date", "production_date"],
        "P3.Specification": ["Specification", "specification"],
        "Production Date_y": ["year-month-day", "Production Date"],
        "Specification_y": ["Specification"],
        "BottomTape": ["BottomTape", "Bottom Tape", "bottom_tape"],
        "P3.Machine_No.": ["Machine NO", "Machine No", "machine_no"],
        "Mold No.": ["Mold NO", "Mold No", "mold_no"],
        "pasteirontemp": ["pasteirontemp"],
        "blowirontemp": ["blowirontemp"],
        "firstAsize": ["firstAsize", "First A Size"],
        "lastAsize": ["lastAsize", "Last A Size"],
        "firstBsize": ["firstBsize", "First B Size"],
        "lastBsize": ["lastBsize", "Last B Size"],
        "Lot_No.": ["Lot_No.", "lot_no", "Lot No"],
        "EValue": ["EValue", "E Value", "E_Value", "e_value"],
        "10PO": ["10PO"],
        "Burr": ["Burr", "burr"],
        "Shift": ["Shift", "shift"],
        "Iron": ["Iron", "iron"],
        "Mold": ["Mold", "mold"],
        "RubberWheel": ["RubberWheel", "Rubber Wheel"],
        "glue": ["glue"],
        "lot": ["lot", "Lot"],
        "AdjustmentRecord": ["AdjustmentRecord", "Adjustment Record"],
        "Finish": ["Finish", "finish"],
        "operator": ["operator", "Operator"],
        "Produce_No.": ["Produce_No.", "Product_ID", "product_id"],
    }

    for target_col, source_cols in p3_field_mapping.items():
        merged[target_col] = _get_first_match(p3_row, source_cols)

    return merged


def _get_first_match(data: dict[str, Any], keys: list[str]) -> Any:
    """從 dict 中找第一個存在的 key 的值"""
    if not data:
        return None
    for key in keys:
        if key in data and data[key] is not None and data[key] != "":
            return data[key]
    return None


# ==============================================================================
# Station-specific Data Fetch (for NG drill-down)
# ==============================================================================


async def fetch_p2_ng_records_from_db(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    ng_value: int = 0,
) -> list[dict[str, Any]]:
    """
    從資料庫撈取 P2 NG 資料（Striped Results = 0）。

    Args:
        db: AsyncSession
        tenant_id: 租戶 ID
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        ng_value: NG 值（預設為 0）

    Returns:
        list[dict]: NG 資料列表
    """
    from app.models.p2_item_v2 import P2ItemV2
    from app.models.p2_record import P2Record

    start_yyyymmdd = parse_date_string_to_yyyymmdd(start_date)
    end_yyyymmdd = parse_date_string_to_yyyymmdd(end_date)

    stmt = (
        select(P2ItemV2)
        .join(P2Record, P2ItemV2.p2_record_id == P2Record.id)
        .where(
            P2ItemV2.tenant_id == tenant_id,
            P2ItemV2.slitting_result == ng_value,
        )
        .options(selectinload(P2ItemV2.p2_record))
    )

    result = await db.execute(stmt)
    p2_items = result.scalars().all()

    records: list[dict[str, Any]] = []
    for p2_item in p2_items:
        row_data = p2_item.row_data or {}

        # Apply date filter on slitting date
        slitting_date_raw = extract_p2_slitting_date(row_data)
        slitting_yyyymmdd = parse_p2_slitting_date_to_yyyymmdd(slitting_date_raw)

        if start_yyyymmdd is not None or end_yyyymmdd is not None:
            if not is_date_in_range(slitting_yyyymmdd, start_yyyymmdd, end_yyyymmdd):
                continue

        records.append(
            {
                "id": str(p2_item.id),
                "lot_no_raw": p2_item.p2_record.lot_no_raw
                if p2_item.p2_record
                else None,
                "winder_number": p2_item.winder_number,
                "slitting_result": p2_item.slitting_result,
                "slitting_date": slitting_date_raw,
                "row_data": row_data,
            }
        )

    return records
