"""Backfill P2ItemV2.trace_lot_no from lot_no_raw(7+2) + winder(2).

Usage:
  cd form-analysis-server/backend
  python -m scripts.manual.backfill_p2_trace_lot_no
"""

from __future__ import annotations

import asyncio
import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db_context, init_db
from app.models.p2_item_v2 import P2ItemV2
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


def _compose_trace_lot_no(lot_7_2: str | None, winder: int | None) -> str | None:
    if not lot_7_2 or winder is None:
        return None
    try:
        w = int(winder)
    except (TypeError, ValueError):
        return None
    if w <= 0:
        return None
    return f"{lot_7_2}_{w:02d}"


async def main() -> None:
    await init_db()

    async with get_db_context() as db:
        stmt = select(P2Record).options(selectinload(P2Record.items_v2))
        result = await db.execute(stmt)
        records = result.scalars().unique().all()

        scanned = 0
        updated = 0
        skipped = 0

        for record in records:
            lot_7_2 = _canonicalize_lot_7_2(getattr(record, "lot_no_raw", None))
            items = list(getattr(record, "items_v2", None) or [])
            for item in items:
                scanned += 1
                trace = _compose_trace_lot_no(lot_7_2, getattr(item, "winder_number", None))
                if not trace:
                    skipped += 1
                    continue
                if getattr(item, "trace_lot_no", None) == trace:
                    continue
                item.trace_lot_no = trace
                updated += 1

        await db.commit()
        print(f"scanned={scanned} updated={updated} skipped={skipped}")


if __name__ == "__main__":
    # psycopg async on Windows requires selector event loop policy.
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

