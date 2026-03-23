import argparse
import asyncio
import os
import sys
from typing import Optional

from sqlalchemy import delete, func, select

# Keep consistent with other backend scripts in this repo
# Allow overriding via environment variable, but provide a sensible local default.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db",
)

# Ensure we can import the backend package when running as a script
sys.path.append(os.getcwd())

from app.core import database
from app.models.record import Record
from app.models.p3_item import P3Item
from app.models.p3_record import P3Record


def _unknown_filter(column):
    # Case-insensitive match for any 'unknown' substring
    # Works on PostgreSQL and SQLite.
    return func.lower(column).like("%unknown%")


async def _count(session, model, where_clause) -> int:
    stmt = select(func.count()).select_from(model).where(where_clause)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def _sample(session, model, where_clause, limit: int = 10):
    stmt = select(model).where(where_clause).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


async def run(apply: bool, include_records: bool) -> None:
    await database.init_db()

    async with database.async_session_factory() as session:
        p3_items_where = (P3Item.product_id.is_not(None)) & _unknown_filter(P3Item.product_id)
        p3_records_where = (P3Record.product_id.is_not(None)) & _unknown_filter(P3Record.product_id)
        records_where = (Record.product_id.is_not(None)) & _unknown_filter(Record.product_id)

        p3_items_count = await _count(session, P3Item, p3_items_where)
        p3_records_count = await _count(session, P3Record, p3_records_where)
        records_count = await _count(session, Record, records_where) if include_records else 0

        print("=== Unknown product_id cleanup ===")
        print(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")
        if include_records:
            print(f"Targets: p3_items={p3_items_count}, p3_records={p3_records_count}, records(all)={records_count}")
        else:
            print(f"Targets: p3_items={p3_items_count}, p3_records={p3_records_count}")
        print(f"Mode: {'APPLY (DELETE)' if apply else 'DRY-RUN (NO DELETE)'}")

        if p3_items_count:
            print("\n--- Sample p3_items (product_id contains 'unknown') ---")
            for item in await _sample(session, P3Item, p3_items_where):
                print(f"- id={item.id} record_id={item.record_id} product_id={item.product_id}")

        if p3_records_count:
            print("\n--- Sample p3_records (product_id contains 'unknown') ---")
            for rec in await _sample(session, P3Record, p3_records_where):
                print(f"- id={rec.id} tenant_id={rec.tenant_id} product_id={rec.product_id} lot_no_norm={rec.lot_no_norm}")

        if include_records and records_count:
            print("\n--- Sample records (any type, product_id contains 'unknown') ---")
            for rec in await _sample(session, Record, records_where):
                print(f"- id={rec.id} lot_no={rec.lot_no} product_id={rec.product_id} production_date={rec.production_date}")

        if not apply:
            print("\nDry-run complete. Re-run with --apply to delete.")
            return

        # Delete order: children first (p3_items), then legacy records (optional), then p3_records.
        # p3_items have FK to records; deleting items is safe and does not delete parent records.
        deleted_p3_items = 0
        deleted_p3_records = 0
        deleted_records = 0

        if p3_items_count:
            result = await session.execute(delete(P3Item).where(p3_items_where))
            deleted_p3_items = int(result.rowcount or 0)

        if p3_records_count:
            result = await session.execute(delete(P3Record).where(p3_records_where))
            deleted_p3_records = int(result.rowcount or 0)

        if include_records and records_count:
            result = await session.execute(delete(Record).where(records_where))
            deleted_records = int(result.rowcount or 0)

        await session.commit()

        print("\n=== Deleted ===")
        print(f"p3_items: {deleted_p3_items}")
        print(f"p3_records: {deleted_p3_records}")
        if include_records:
            print(f"records(all): {deleted_records}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Delete rows whose product_id contains 'unknown' (case-insensitive). Default is dry-run."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete rows (otherwise dry-run).",
    )
    parser.add_argument(
        "--include-records",
        action="store_true",
        help="Also delete from legacy records table.",
    )
    args = parser.parse_args(argv)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run(apply=args.apply, include_records=args.include_records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
