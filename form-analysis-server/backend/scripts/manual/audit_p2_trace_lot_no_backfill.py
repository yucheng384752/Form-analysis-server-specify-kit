"""Audit why P2 trace_lot_no backfill updated=0.

Classifies each P2 item into:
  - already_filled
  - missing_lot_no_raw
  - invalid_lot_no_raw_format
  - missing_winder_number
  - invalid_winder_number
  - fillable

Usage:
  cd form-analysis-server/backend
  python -m scripts.manual.audit_p2_trace_lot_no_backfill
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db_context, init_db
from app.models.p2_record import P2Record


LOT_7_2_PATTERN = re.compile(r"^(\d{7})[-_](\d{1,2})(?:[-_].+)?$")


def _canonicalize_lot_7_2(raw: str | None) -> str | None:
    s = str(raw or "").strip()
    if not s:
        return None
    m = LOT_7_2_PATTERN.match(s)
    if not m:
        return None
    return f"{m.group(1)}_{m.group(2).zfill(2)}"


def _classify_item(record: P2Record, item) -> str:
    existing = str(getattr(item, "trace_lot_no", "") or "").strip()
    if existing:
        return "already_filled"

    lot_raw = getattr(record, "lot_no_raw", None)
    lot_7_2 = _canonicalize_lot_7_2(lot_raw)
    if str(lot_raw or "").strip() == "":
        return "missing_lot_no_raw"
    if not lot_7_2:
        return "invalid_lot_no_raw_format"

    winder = getattr(item, "winder_number", None)
    if winder is None:
        return "missing_winder_number"
    try:
        winder_i = int(winder)
    except (TypeError, ValueError):
        return "invalid_winder_number"
    if winder_i <= 0:
        return "invalid_winder_number"

    return "fillable"


async def main() -> None:
    await init_db()
    async with get_db_context() as db:
        stmt = select(P2Record).options(selectinload(P2Record.items_v2))
        result = await db.execute(stmt)
        records = result.scalars().unique().all()

        counter: Counter[str] = Counter()
        sample: dict[str, list[str]] = {}
        scanned = 0

        for record in records:
            for item in list(getattr(record, "items_v2", None) or []):
                scanned += 1
                category = _classify_item(record, item)
                counter[category] += 1
                if len(sample.get(category, [])) < 5:
                    sample.setdefault(category, []).append(
                        f"record_id={getattr(record, 'id', '')} item_id={getattr(item, 'id', '')} "
                        f"lot_no_raw={getattr(record, 'lot_no_raw', None)} winder={getattr(item, 'winder_number', None)} "
                        f"trace_lot_no={getattr(item, 'trace_lot_no', None)}"
                    )

        print(f"scanned={scanned}")
        for key in [
            "already_filled",
            "fillable",
            "missing_lot_no_raw",
            "invalid_lot_no_raw_format",
            "missing_winder_number",
            "invalid_winder_number",
        ]:
            print(f"{key}={counter.get(key, 0)}")

        print("\nexamples:")
        for key in [
            "already_filled",
            "fillable",
            "missing_lot_no_raw",
            "invalid_lot_no_raw_format",
            "missing_winder_number",
            "invalid_winder_number",
        ]:
            rows = sample.get(key, [])
            if not rows:
                continue
            print(f"\n[{key}]")
            for row in rows:
                print(row)


if __name__ == "__main__":
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

