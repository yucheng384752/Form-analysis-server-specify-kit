"""Fix Product ID format to the single canonical underscore format.

Canonical format: YYYYMMDD_machine_mold_lot[_suffix]

This script updates existing database rows that still use the legacy hyphen-delimited
format (e.g. 20250902-P24-238-2-301) into the canonical format
(e.g. 20250902_P24_238-2_301).

Usage:
  python scripts/fix_product_id_format_to_underscore.py --dry-run
  python scripts/fix_product_id_format_to_underscore.py --apply

Notes:
- Only the TOP-LEVEL delimiters are converted (date/machine/mold/lot).
- Mold values may contain '-' and are preserved.
- Mixed IDs like 20250902-P24-238-2-301_dup9 will be normalized to
  20250902_P24_238-2_301_dup9.
"""

# pyright: reportMissingImports=false

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Optional, Tuple

from sqlalchemy import select

# Ensure we can import the FastAPI backend package when running from repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(REPO_ROOT, "form-analysis-server", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.core.database import close_db, get_db_context, init_db


LEGACY_HYPHEN_BASE_RE = re.compile(r"^(\d{8})-([A-Za-z0-9]+)-(.+)-(\d+)$")


def _split_base_and_suffix(product_id: str) -> Tuple[str, Optional[str]]:
    # We only treat `_dup...` as suffix convention; if there are other underscores
    # they are assumed to be part of canonical already.
    if "_dup" in product_id:
        base, suffix = product_id.split("_dup", 1)
        return base, "dup" + suffix
    if "_" in product_id and "-" in product_id and product_id.count("_") >= 1:
        # Mixed IDs might have arbitrary underscore suffixes; keep everything after the first underscore
        # only if the prefix is legacy-hyphen.
        first_underscore = product_id.find("_")
        return product_id[:first_underscore], product_id[first_underscore + 1 :]
    return product_id, None


def normalize_product_id(product_id: Optional[str]) -> Optional[str]:
    """Return normalized product_id, or None if no change needed."""
    if not product_id or not isinstance(product_id, str):
        return None

    # Already canonical (must contain underscore delimiter between date and machine)
    if re.match(r"^\d{8}_[^_]+_", product_id):
        return None

    base, suffix = _split_base_and_suffix(product_id)

    if not base or "-" not in base:
        return None

    # Parse legacy base: date-machine-mold-lot, where mold may contain '-'
    parts = base.split("-")
    if len(parts) < 4:
        return None

    date_str = parts[0]
    machine = parts[1]

    lot_idx = -1
    for i in range(len(parts) - 1, 1, -1):
        if parts[i].isdigit():
            lot_idx = i
            break

    if lot_idx == -1:
        return None

    lot = parts[lot_idx]
    mold = "-".join(parts[2:lot_idx]) if lot_idx > 2 else parts[2]

    if not re.match(r"^\d{8}$", date_str):
        return None

    new_id = f"{date_str}_{machine}_{mold}_{lot}"
    if suffix:
        new_id = f"{new_id}_{suffix}"
    return new_id


async def main_async(apply: bool) -> int:
    await init_db()

    updated = 0
    scanned = 0

    # Import models lazily (after init_db) to avoid import-time side effects.
    from app.models.p3_record import P3Record
    from app.models.p3_item_v2 import P3ItemV2
    from app.models.p3_item import P3Item
    from app.models.record import Record

    async with get_db_context() as db:
        for model, field_name in [
            (P3Record, "product_id"),
            (P3ItemV2, "product_id"),
            (P3Item, "product_id"),
            (Record, "product_id"),
        ]:
            result = await db.execute(select(model))
            rows = result.scalars().all()

            for row in rows:
                scanned += 1
                current = getattr(row, field_name, None)
                new_id = normalize_product_id(current)
                if not new_id:
                    continue

                # Collision check (best-effort)
                collision_stmt = select(model).where(getattr(model, field_name) == new_id)
                collision = (await db.execute(collision_stmt)).scalar_one_or_none()
                if collision is not None:
                    print(f"[SKIP] collision in {model.__tablename__}: {current} -> {new_id}")
                    continue

                print(f"[{model.__tablename__}] {current} -> {new_id}")
                updated += 1
                if apply:
                    setattr(row, field_name, new_id)

    await close_db()
    print(f"Scanned: {scanned}, Updated: {updated}, Apply: {apply}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply updates to DB")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without applying")
    args = parser.parse_args()

    if args.apply and args.dry_run:
        raise SystemExit("Use only one of --apply or --dry-run")

    apply = bool(args.apply)
    if not apply and not args.dry_run:
        args.dry_run = True

    import asyncio

    return asyncio.run(main_async(apply=apply))


if __name__ == "__main__":
    raise SystemExit(main())
