"""QC CSV 解析與匯入服務

CSV 來自 PDF server /process?table=QC，格式為：
每機台 3 行（判定行、H行、L行），欄位：
  A值_H, A值_L, B值_H, B值_L, E'值_H, E'值_L, 10P0值_H, 10P0值_L,
  彎曲, 備註, A值, B値, E'値, 10P0値,
  生產捲數1, 機台, 生產捲數2~9, 不良原因說明
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from typing import Any

from app.core.logging import get_logger
from app.models.qc_record import QcRecord

logger = get_logger(__name__)

# 判斷 OK/NG 的判定記號
_OK_MARKS = {"v", "✓", "√", "o", "ok", "pass"}
_NG_MARKS = {"x", "✗", "ng", "fail", "×"}


def _is_ok(val: str) -> bool:
    return val.strip().lower() in _OK_MARKS


def _is_ng(val: str) -> bool:
    return val.strip().lower() in _NG_MARKS


def _to_float(val: str) -> float | None:
    """容錯解析 OCR 誤差數字（例如 '1-005' → 1.005, '04610' → 0.4610）"""
    if not val:
        return None
    s = val.strip()
    if not s:
        return None
    # 以連字號作小數點（OCR常見錯誤）
    s = re.sub(r"(?<=\d)-(?=\d)", ".", s)
    # 移除前置$、yo.等非數字前綴
    s = re.sub(r"^[^0-9.+-]+", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(val: str) -> int | None:
    f = _to_float(val)
    if f is None:
        return None
    try:
        return int(round(f))
    except (ValueError, OverflowError):
        return None


def _parse_date_from_filename(filename: str) -> date | None:
    """從 QC_260401.pdf 解析日期 → 2026-04-01"""
    m = re.search(r"(\d{6})", filename)
    if not m:
        return None
    s = m.group(1)  # YYMMDD（民國或西元後兩碼）
    try:
        yy, mm, dd = int(s[:2]), int(s[2:4]), int(s[4:6])
        # 民國年 → 西元：yy + 1911，若 < 1911 代表近年西元
        if yy < 50:
            yy += 2000
        else:
            yy += 1911  # 民國年
        return date(yy, mm, dd)
    except (ValueError, TypeError):
        return None


def _roll_val_to_thickness(val: str) -> int | None:
    """把捲數欄的數值字串轉為 int 厚度，非數字（判定符號）回傳 None"""
    if not val.strip():
        return None
    if _is_ok(val) or _is_ng(val):
        return None
    return _to_int(val)


def parse_qc_csv(csv_text: str, source_file: str = "") -> list[dict[str, Any]]:
    """解析 QC CSV，回傳每機台的結構化 dict 清單。"""
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = [row for row in reader]

    ROLL_COLS = [f"生產捲數{i}" for i in range(1, 10)]
    MACHINE_COL = "機台"
    BAD_REASON_COL = "不良原因說明"
    BENDING_COL = "彎曲"
    REMARK_COL = "備註"
    A_COL = "A值"
    B_COL = "B值"
    E_COL = "E'值"
    P0_COL = "10P0值"

    production_date = _parse_date_from_filename(source_file)
    results: list[dict[str, Any]] = []

    i = 0
    while i < len(rows):
        row = rows[i]

        # 找到機台欄有值的行（判定行）
        machine = (row.get(MACHINE_COL) or "").strip()
        if not machine:
            i += 1
            continue

        # 判定行
        judgment_row = row
        h_row = rows[i + 1] if i + 1 < len(rows) else {}
        l_row = rows[i + 2] if i + 2 < len(rows) else {}

        # --- 機台名稱 ---
        machine_no = machine

        # --- 備註 / result ---
        qc_result_raw = (judgment_row.get(REMARK_COL) or "").strip()
        # 標準化：No NG, 1NG, NG...
        if re.match(r"no\s*ng|no\s*mig|no\s*hg|no\s*nc", qc_result_raw, re.I):
            qc_result = "No NG"
        elif re.match(r"\d+\s*ng", qc_result_raw, re.I):
            m = re.match(r"(\d+)\s*ng", qc_result_raw, re.I)
            qc_result = f"{m.group(1)}NG" if m else qc_result_raw
        elif qc_result_raw:
            qc_result = qc_result_raw
        else:
            qc_result = None

        # --- 不良原因 ---
        bad_reason = (judgment_row.get(BAD_REASON_COL) or "").strip() or None

        # --- QC H 值（來自判定行 A値/B値/E'値/10P0値 欄）---
        qc_A_H = _to_float(judgment_row.get(A_COL) or "")
        qc_B_H = _to_float(judgment_row.get(B_COL) or "")
        qc_E_H = _to_float(judgment_row.get(E_COL) or "")
        qc_10P0_H = _to_float(judgment_row.get(P0_COL) or "")

        # --- QC L 值（來自 L 行相同欄位）---
        qc_A_L = _to_float(l_row.get(A_COL) or "")
        qc_B_L = _to_float(l_row.get(B_COL) or "")
        qc_E_L = _to_float(l_row.get(E_COL) or "")
        qc_10P0_L = _to_float(l_row.get(P0_COL) or "")

        # 若 CSV 已有 _H/_L 分開欄位則優先使用
        if judgment_row.get("A值_H"):
            qc_A_H = _to_float(judgment_row["A值_H"]) or qc_A_H
        if judgment_row.get("A值_L"):
            qc_A_L = _to_float(judgment_row["A值_L"]) or qc_A_L

        # --- 彎曲：取 H 行或 L 行第一個非空值 ---
        bending_raw = (h_row.get(BENDING_COL) or l_row.get(BENDING_COL) or "").strip()
        qc_bending = _to_int(bending_raw)

        # --- 生產捲數 ---
        rolls: list[dict[str, Any]] = []
        for idx, col in enumerate(ROLL_COLS):
            j_val = (judgment_row.get(col) or "").strip()
            h_val = (h_row.get(col) or "").strip()
            l_val = (l_row.get(col) or "").strip()

            judgment = "OK" if _is_ok(j_val) else ("NG" if _is_ng(j_val) else None)
            th_H = _roll_val_to_thickness(h_val)
            th_L = _roll_val_to_thickness(l_val)

            # 三個欄位都空則代表此卷不存在
            if not j_val and not h_val and not l_val:
                continue

            rolls.append({
                "roll_no": idx + 1,
                "judgment": judgment,
                "thickness_H": th_H,
                "thickness_L": th_L,
            })

        ng_count = sum(1 for r in rolls if r["judgment"] == "NG")

        results.append({
            "production_date": production_date,
            "machine_no": machine_no,
            "source_file": source_file,
            "qc_A_H": qc_A_H,
            "qc_A_L": qc_A_L,
            "qc_B_H": qc_B_H,
            "qc_B_L": qc_B_L,
            "qc_E_prime_H": qc_E_H,
            "qc_E_prime_L": qc_E_L,
            "qc_10P0_H": qc_10P0_H,
            "qc_10P0_L": qc_10P0_L,
            "qc_bending": qc_bending,
            "qc_result": qc_result,
            "ng_count": ng_count,
            "bad_reason": bad_reason,
            "rolls_data": rolls,
        })

        i += 3  # 跳到下一機台

    return results


async def upsert_qc_records(
    db: Any,
    tenant_id: Any,
    records: list[dict[str, Any]],
) -> list[QcRecord]:
    """將解析結果寫入 DB（UPSERT：同機台同日期覆蓋）"""
    from sqlalchemy import select

    saved: list[QcRecord] = []
    for data in records:
        if not data.get("production_date") or not data.get("machine_no"):
            logger.warning("skip qc row missing date or machine: %s", data)
            continue

        stmt = select(QcRecord).where(
            QcRecord.tenant_id == tenant_id,
            QcRecord.production_date == data["production_date"],
            QcRecord.machine_no == data["machine_no"],
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            existing.tenant_id = tenant_id
            saved.append(existing)
        else:
            rec = QcRecord(tenant_id=tenant_id, **data)
            db.add(rec)
            saved.append(rec)

    await db.commit()
    return saved
