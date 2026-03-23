"""Backfill P2ItemV2.production_date_yyyymmdd from row_data.

Usage:
  cd form-analysis-server/backend
  python scripts/manual/backfill_p2_item_dates.py
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select

from app.core.database import get_db_context, init_db
from app.models.p2_item_v2 import P2ItemV2
from app.services.csv_field_mapper import csv_field_mapper


DATE_KEYS = [
    "Slitting date",
    "Slitting Date",
    "slitting date",
    "slitting_date",
    "Slitting Time",
    "slitting_time",
    "分條時間",
    "production_date",
    "Production Date",
    "生產日期",
    "date",
    "Date",
]


def _extract_yyyymmdd_from_row(row: dict[str, Any] | None) -> int | None:
    if not isinstance(row, dict):
        return None

    candidates: list[Any] = []
    for key in DATE_KEYS:
        if key in row and row[key] is not None and str(row[key]).strip():
            candidates.append(row[key])

    nested_rows = row.get("rows")
    if isinstance(nested_rows, list):
        for nested in nested_rows:
            if not isinstance(nested, dict):
                continue
            for key in DATE_KEYS:
                if key in nested and nested[key] is not None and str(nested[key]).strip():
                    candidates.append(nested[key])

    for val in candidates:
        ymd = csv_field_mapper._normalize_date_to_yyyymmdd(str(val))
        if ymd:
            return int(ymd)
    return None


async def main() -> None:
    await init_db()

    async with get_db_context() as db:
        result = await db.execute(
            select(P2ItemV2).where(P2ItemV2.production_date_yyyymmdd.is_(None))
        )
        rows = result.scalars().all()
        scanned = len(rows)
        updated = 0

        for item in rows:
            row_data = item.row_data if isinstance(item.row_data, dict) else None
            ymd = _extract_yyyymmdd_from_row(row_data)
            if not ymd:
                continue
            item.production_date_yyyymmdd = int(ymd)
            updated += 1

        await db.commit()
        print(f"scanned={scanned} updated={updated} skipped={scanned - updated}")


if __name__ == "__main__":
    asyncio.run(main())

