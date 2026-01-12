import argparse
import asyncio
import os
import sys
from typing import Optional

from datetime import date

from sqlalchemy import select

# Default local DB for convenience when running outside docker
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db",
)

sys.path.append(os.getcwd())

from app.core import database
from app.models.record import Record, DataType
from app.models.p3_item import P3Item
from app.models.p3_record import P3Record


def _upper(s: Optional[str]) -> str:
    return (s or "").strip().upper()


def _parse_minguo_ymd(raw: object) -> Optional[date]:
    """Parse strings like '114年09月01日' into a date(2025, 9, 1)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if "年" in s and "月" in s and "日" in s:
            y_str = s.split("年")[0].strip()
            m_str = s.split("年")[1].split("月")[0].strip()
            d_str = s.split("月")[1].split("日")[0].strip()
            y = int(y_str)
            # 民國年轉西元：114 -> 2025
            if y < 1911:
                y += 1911
            return date(y, int(m_str), int(d_str))
    except Exception:
        return None
    return None


def _derive_machine_mold_from_rows(rows: object) -> tuple[Optional[str], Optional[str]]:
    if not isinstance(rows, list) or not rows:
        return None, None
    first = rows[0]
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


def _derive_first_lot_from_rows(rows: object) -> Optional[int]:
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    if not isinstance(first, dict):
        return None
    raw = first.get("lot") or first.get("LOT") or first.get("Lot")
    try:
        return int(float(raw)) if raw is not None else None
    except (ValueError, TypeError):
        return None


async def run(lot_no: Optional[str], apply: bool, fix_date_from_row: bool) -> None:
    await database.init_db()

    async with database.async_session_factory() as session:
        # ---- Fix V2 p3_records ----
        p3_stmt = select(P3Record)
        if lot_no:
            p3_stmt = p3_stmt.where(P3Record.lot_no_raw == lot_no)
        p3_rows = (await session.execute(p3_stmt)).scalars().all()

        p3_to_fix = []
        for r in p3_rows:
            if _upper(r.machine_no) == "UNKNOWN" or _upper(r.mold_no) == "UNKNOWN" or not r.product_id:
                rows = (r.extras or {}).get("rows") if isinstance(r.extras, dict) else None
                machine, mold = _derive_machine_mold_from_rows(rows)
                if machine or mold:
                    p3_to_fix.append((r, machine, mold, _derive_first_lot_from_rows(rows)))

        # ---- Fix legacy p3_items (and their parent Record.lot_no) ----
        item_stmt = select(P3Item, Record).join(Record, P3Item.record_id == Record.id)
        item_stmt = item_stmt.where(Record.data_type == DataType.P3)
        if lot_no:
            item_stmt = item_stmt.where(Record.lot_no == lot_no)
        items = (await session.execute(item_stmt)).all()

        # Track product_ids that are already present (and those we plan to assign) to avoid unique violations.
        existing_pids_stmt = select(P3Item.product_id).where(P3Item.product_id.is_not(None))
        if lot_no:
            existing_pids_stmt = (
                existing_pids_stmt.join(Record, P3Item.record_id == Record.id)
                .where(Record.data_type == DataType.P3, Record.lot_no == lot_no)
            )
        existing_pids = set((await session.execute(existing_pids_stmt)).scalars().all())
        planned_pids: set[str] = set(pid for pid in existing_pids if pid)

        items_to_fix = []
        for item, rec in items:
            # Fix lot_no (bug: was production_lot like 301)
            needs_lot_no_fix = (item.lot_no != rec.lot_no)

            # Fix production_lot
            production_lot = item.production_lot
            if production_lot is None:
                raw = None
                if isinstance(item.row_data, dict):
                    raw = item.row_data.get("lot") or item.row_data.get("LOT") or item.row_data.get("Lot")
                else:
                    raw = None
                try:
                    production_lot = int(float(raw)) if raw is not None else None
                except (ValueError, TypeError):
                    production_lot = None

            # Fix production_date
            parsed_row_date = None
            if fix_date_from_row and isinstance(item.row_data, dict):
                parsed_row_date = _parse_minguo_ymd(item.row_data.get("year-month-day"))

            prod_date = parsed_row_date or item.production_date or rec.production_date
            needs_prod_date_fix = (
                fix_date_from_row
                and parsed_row_date is not None
                and item.production_date is not None
                and item.production_date != parsed_row_date
            )

            # Fix product_id
            needs_pid_fix = (not item.product_id) or ("UNKNOWN" in _upper(item.product_id))
            new_pid = None
            if needs_pid_fix and prod_date and item.machine_no and item.mold_no and production_lot is not None:
                date_str = prod_date.strftime("%Y%m%d")
                base = f"{date_str}_{str(item.machine_no).strip()}_{str(item.mold_no).strip()}_{int(production_lot)}"
                candidate = base
                if candidate in planned_pids and candidate != (item.product_id or ""):
                    # parser tolerates suffix; make it deterministic by row_no and counter
                    counter = 1
                    candidate = f"{base}_dup{item.row_no}"
                    while candidate in planned_pids and candidate != (item.product_id or ""):
                        counter += 1
                        candidate = f"{base}_dup{item.row_no}_{counter}"
                new_pid = candidate
                planned_pids.add(new_pid)

            if (
                needs_lot_no_fix
                or (item.production_lot is None and production_lot is not None)
                or (item.production_date is None and prod_date is not None)
                or needs_prod_date_fix
                or new_pid
            ):
                items_to_fix.append((item, rec, needs_lot_no_fix, production_lot, prod_date, new_pid))

        print("=== P3 backfill/repair ===")
        print(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")
        print(f"Filter lot_no: {lot_no or '(none)'}")
        print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
        print(f"p3_records candidates: {len(p3_rows)}; to_fix: {len(p3_to_fix)}")
        print(f"p3_items candidates: {len(items)}; to_fix: {len(items_to_fix)}")

        if p3_to_fix:
            print("\n--- Sample p3_records fixes (up to 5) ---")
            for r, machine, mold, lot_val in p3_to_fix[:5]:
                print(
                    f"- id={r.id} lot_no_raw={r.lot_no_raw} date={r.production_date_yyyymmdd} "
                    f"machine {r.machine_no}->{machine or r.machine_no} mold {r.mold_no}->{mold or r.mold_no} "
                    f"product_id={r.product_id} first_lot={lot_val}"
                )

        if items_to_fix:
            print("\n--- Sample p3_items fixes (up to 5) ---")
            for item, rec, lot_fix, pl, pd, pid in items_to_fix[:5]:
                print(
                    f"- id={item.id} record_id={rec.id} lot_no {item.lot_no}->{rec.lot_no if lot_fix else item.lot_no} "
                    f"production_lot {item.production_lot}->{pl} production_date {item.production_date}->{pd} "
                    f"product_id {item.product_id}->{pid or item.product_id}"
                )

        if not apply:
            print("\nDry-run complete. Re-run with --apply to write changes.")
            return

        # Apply changes
        for r, machine, mold, lot_val in p3_to_fix:
            if machine and _upper(r.machine_no) == "UNKNOWN":
                r.machine_no = machine
            if mold and _upper(r.mold_no) == "UNKNOWN":
                r.mold_no = mold
            if not r.product_id:
                # Store a representative product_id (first lot) to aid lookup
                lot_part = lot_val or 0
                r.product_id = f"{r.production_date_yyyymmdd}_{r.machine_no}_{r.mold_no}_{lot_part}"

        for item, rec, lot_fix, pl, pd, pid in items_to_fix:
            if lot_fix:
                item.lot_no = rec.lot_no
            if item.production_lot is None and pl is not None:
                item.production_lot = pl
            if pd is not None:
                if item.production_date is None:
                    item.production_date = pd
                elif fix_date_from_row and item.production_date != pd:
                    item.production_date = pd
            if pid:
                item.product_id = pid

        await session.commit()
        print("\nAPPLY complete.")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill/repair P3 data: fix UNKNOWN machine/mold on p3_records, and fix lot_no/production_lot/product_id on legacy p3_items."
    )
    parser.add_argument("--lot-no", help="Target a specific lot_no (e.g. 2507173_02)")
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry-run)")
    parser.add_argument(
        "--fix-date-from-row",
        action="store_true",
        help="Also fix p3_items.production_date from row_data['year-month-day'] when present.",
    )
    args = parser.parse_args(argv)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run(lot_no=args.lot_no, apply=args.apply, fix_date_from_row=args.fix_date_from_row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
