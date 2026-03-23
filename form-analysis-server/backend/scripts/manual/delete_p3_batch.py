"""Delete P3 data for a specific batch safely (dry-run by default).

This script is intentionally conservative:
- Shows counts and a few sample rows first
- Does NOT delete unless you pass --yes

Supports three selection modes (choose exactly one):
1) By lot_no_raw (e.g. spurious lot like "0902_P02")
2) By product_id prefix (e.g. "20250902_P02")
3) By production_date_yyyymmdd + machine_no (e.g. 20250902 + P02)

Multi-tenant safety:
- You must specify --tenant-id or --tenant-code, OR pass --all-tenants.

Notes:
- Deletes from new tables: p3_records (cascades to p3_items_v2).
- Optionally deletes legacy tables: records + p3_items when --delete-legacy is set.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import and_, delete, func, or_, select


DEFAULT_DATABASE_URL = "postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db"


@dataclass(frozen=True)
class TenantScope:
    tenant_ids: Optional[list[uuid.UUID]]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete P3 batch data (dry-run by default).")

    scope = parser.add_argument_group("Tenant scope")
    scope.add_argument("--tenant-id", dest="tenant_id", help="Target tenant UUID")
    scope.add_argument("--tenant-code", dest="tenant_code", help="Target tenant code (tenants.code)")
    scope.add_argument(
        "--all-tenants",
        action="store_true",
        help="Allow deletion across all tenants (dangerous; requires --yes too).",
    )

    selector = parser.add_argument_group("Selection (choose exactly one mode)")
    selector.add_argument("--lot-no-raw", dest="lot_no_raw", help="Match P3Record.lot_no_raw exactly")
    selector.add_argument(
        "--match-lot-norm",
        action="store_true",
        help="When using --lot-no-raw, also match by normalized digits (lot_no_norm).",
    )
    selector.add_argument(
        "--product-id-prefix",
        dest="product_id_prefix",
        help="Match P3Record.product_id by prefix (e.g. 20250902_P02)",
    )
    selector.add_argument(
        "--production-date",
        dest="production_date",
        type=int,
        help="Match P3Record.production_date_yyyymmdd (YYYYMMDD, e.g. 20250902)",
    )
    selector.add_argument(
        "--machine-no",
        dest="machine_no",
        help="Match P3Record.machine_no (e.g. P02)",
    )

    misc = parser.add_argument_group("Options")
    misc.add_argument(
        "--delete-legacy",
        action="store_true",
        help="Also delete legacy tables (records + p3_items) for the same selector when possible.",
    )
    misc.add_argument(
        "--database-url",
        dest="database_url",
        default=None,
        help=f"Override DATABASE_URL (default: {DEFAULT_DATABASE_URL})",
    )
    misc.add_argument(
        "--yes",
        action="store_true",
        help="Actually perform deletion. Without this flag, script is dry-run only.",
    )

    return parser.parse_args()


def _selection_mode(args: argparse.Namespace) -> str:
    modes = []
    if args.lot_no_raw:
        modes.append("lot")
    if args.product_id_prefix:
        modes.append("product_prefix")
    if args.production_date is not None or args.machine_no is not None:
        # counts as a mode only if both are present
        if args.production_date is not None or args.machine_no is not None:
            modes.append("date_machine")

    # date_machine mode requires both values
    if (args.production_date is None) ^ (args.machine_no is None):
        raise SystemExit("Error: --production-date and --machine-no must be provided together.")

    # Remove date_machine marker if neither is provided
    if args.production_date is None and args.machine_no is None:
        modes = [m for m in modes if m != "date_machine"]

    if len(modes) != 1:
        raise SystemExit(
            "Error: choose exactly one selection mode: "
            "--lot-no-raw OR --product-id-prefix OR (--production-date + --machine-no)."
        )
    return modes[0]


def _ensure_scope(args: argparse.Namespace) -> TenantScope:
    provided = [bool(args.tenant_id), bool(args.tenant_code), bool(args.all_tenants)]
    if sum(provided) != 1:
        raise SystemExit("Error: specify exactly one of --tenant-id, --tenant-code, or --all-tenants")

    if args.all_tenants:
        return TenantScope(tenant_ids=None)

    # we resolve tenant -> tenant_ids in DB
    return TenantScope(tenant_ids=[])


def _pretty(n: int) -> str:
    return f"{n:,}"


async def _resolve_tenant_ids(scope: TenantScope, *, tenant_id: Optional[str], tenant_code: Optional[str]):
    # Deferred imports so this script can be imported without app deps loaded
    from app.core import database
    from app.models.core.tenant import Tenant

    if scope.tenant_ids is None:
        return None

    async with database.async_session_factory() as session:
        if tenant_id:
            try:
                tenant_uuid = uuid.UUID(str(tenant_id))
            except ValueError as e:
                raise SystemExit(f"Error: invalid --tenant-id: {tenant_id} ({e})")

            row = await session.execute(select(Tenant.id).where(Tenant.id == tenant_uuid))
            tid = row.scalar_one_or_none()
            if not tid:
                raise SystemExit(f"Error: tenant not found for id={tenant_id}")
            return [tid]

        row = await session.execute(select(Tenant.id).where(Tenant.code == tenant_code))
        tid = row.scalar_one_or_none()
        if not tid:
            raise SystemExit(f"Error: tenant not found for code={tenant_code}")
        return [tid]


def _iter_chunks(values: Iterable[uuid.UUID], size: int = 500):
    chunk: list[uuid.UUID] = []
    for v in values:
        chunk.append(v)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


async def _count_p3_items_v2_for_records(record_ids: list[uuid.UUID]) -> int:
    from app.core import database
    from app.models.p3_item_v2 import P3ItemV2

    if not record_ids:
        return 0

    total = 0
    async with database.async_session_factory() as session:
        for chunk in _iter_chunks(record_ids, 500):
            stmt = select(func.count()).select_from(P3ItemV2).where(P3ItemV2.p3_record_id.in_(chunk))
            total += int((await session.execute(stmt)).scalar_one())
    return total


async def main() -> None:
    args = _parse_args()
    mode = _selection_mode(args)
    scope = _ensure_scope(args)

    database_url = args.database_url or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
    os.environ["DATABASE_URL"] = database_url

    # Ensure backend app import works when running from repo root or backend root
    sys.path.append(os.getcwd())

    from app.core import database
    from app.models.p3_record import P3Record

    await database.init_db()

    tenant_ids = await _resolve_tenant_ids(scope, tenant_id=args.tenant_id, tenant_code=args.tenant_code)

    # Build selector
    selector_clauses = []
    selector_desc = ""

    if mode == "lot":
        selector_desc = f"lot_no_raw == {args.lot_no_raw!r}"
        selector_clauses.append(P3Record.lot_no_raw == args.lot_no_raw)

        if args.match_lot_norm:
            from app.utils.normalization import normalize_lot_no

            try:
                lot_norm = normalize_lot_no(args.lot_no_raw)
            except Exception as e:
                raise SystemExit(f"Error: cannot normalize lot '{args.lot_no_raw}': {e}")

            selector_desc += f" OR lot_no_norm == {lot_norm}"
            selector_clauses.append(P3Record.lot_no_norm == lot_norm)

        p3_selector = or_(*selector_clauses)

    elif mode == "product_prefix":
        prefix = str(args.product_id_prefix).strip()
        if not prefix:
            raise SystemExit("Error: --product-id-prefix cannot be empty")
        selector_desc = f"product_id startswith {prefix!r}"
        p3_selector = P3Record.product_id.like(prefix + "%")

    else:
        selector_desc = f"production_date_yyyymmdd == {args.production_date} AND machine_no == {args.machine_no!r}"
        p3_selector = and_(
            P3Record.production_date_yyyymmdd == int(args.production_date),
            P3Record.machine_no == str(args.machine_no).strip(),
        )

    where_parts = [p3_selector]
    if tenant_ids is not None:
        where_parts.append(P3Record.tenant_id.in_(tenant_ids))
    where_all = and_(*where_parts)

    # Preview
    async with database.async_session_factory() as session:
        id_rows = await session.execute(select(P3Record.id).where(where_all))
        record_ids = list(id_rows.scalars().all())

        count_records = len(record_ids)

        # Sample rows
        sample_rows = []
        if record_ids:
            sample_stmt = (
                select(P3Record.id, P3Record.tenant_id, P3Record.production_date_yyyymmdd, P3Record.machine_no, P3Record.mold_no, P3Record.lot_no_raw, P3Record.product_id)
                .where(P3Record.id.in_(record_ids[:50]))
                .limit(5)
            )
            sample_rows = (await session.execute(sample_stmt)).all()

    count_items_v2 = await _count_p3_items_v2_for_records(record_ids)

    print("\n=== P3 Deletion Preview ===")
    print(f"DATABASE_URL: {database_url}")
    print(
        f"Scope: {'ALL TENANTS' if tenant_ids is None else 'tenants=' + ','.join(str(t) for t in tenant_ids)}"
    )
    print(f"Selector: {selector_desc}")
    print(f"Matches: p3_records={_pretty(count_records)}, p3_items_v2~={_pretty(count_items_v2)}")

    if sample_rows:
        print("\nSample p3_records (up to 5):")
        for r in sample_rows:
            rid, tid, ymd, mach, mold, lot_raw, pid = r
            print(f"- id={rid} tenant={tid} date={ymd} machine={mach} mold={mold} lot_raw={lot_raw} product_id={pid}")

    if not args.yes:
        print("\nDRY-RUN: no data deleted. Re-run with --yes to confirm.")
        return

    if tenant_ids is None and not args.all_tenants:
        # unreachable, but keep for paranoia
        raise SystemExit("Refusing to delete across all tenants without --all-tenants")

    if tenant_ids is None and args.all_tenants:
        print("\nWARNING: deleting across ALL tenants")

    if count_records == 0:
        print("\nNothing to delete.")
        return

    # Delete new tables
    async with database.async_session_factory() as session:
        await session.execute(delete(P3Record).where(where_all))
        await session.commit()

    print("\nDeleted p3_records (p3_items_v2 should cascade via FK ondelete=CASCADE).")

    # Optional legacy deletion
    if args.delete_legacy:
        from app.models.record import DataType, Record
        from app.models.p3_item import P3Item

        legacy_items_where = []
        legacy_records_where = []
        legacy_desc = ""

        if mode == "lot":
            legacy_desc = f"records.lot_no == {args.lot_no_raw!r} AND data_type == P3"
            legacy_records_where.append(Record.lot_no == args.lot_no_raw)
            legacy_records_where.append(Record.data_type == DataType.P3)
            legacy_items_where.append(P3Item.lot_no == args.lot_no_raw)

        elif mode == "product_prefix":
            legacy_desc = f"p3_items.product_id startswith {args.product_id_prefix!r}"
            legacy_items_where.append(P3Item.product_id.like(str(args.product_id_prefix).strip() + "%"))

        else:
            # Legacy schema uses Record.production_date (date) and Record.machine_no
            # We can only approximate by product_id prefix if available.
            prefix = f"{int(args.production_date):08d}_{str(args.machine_no).strip()}"
            legacy_desc = f"p3_items.product_id startswith {prefix!r} (approx)"
            legacy_items_where.append(P3Item.product_id.like(prefix + "%"))

        # If tenant specified, legacy tables don't have tenant_id; so we can't scope safely.
        if tenant_ids is not None:
            print("\nNOTE: legacy tables are not tenant-scoped; --delete-legacy will delete globally.")

        async with database.async_session_factory() as session:
            # Count first
            legacy_count_items = int(
                (
                    await session.execute(
                        select(func.count()).select_from(P3Item).where(and_(*legacy_items_where))
                    )
                ).scalar_one()
            )
            print(f"\nLegacy selector: {legacy_desc}")
            print(f"Legacy matches: p3_items={_pretty(legacy_count_items)}")

            if legacy_count_items:
                await session.execute(delete(P3Item).where(and_(*legacy_items_where)))
                # If mode == lot, also delete parent records rows for that lot/type
                if mode == "lot" and legacy_records_where:
                    await session.execute(delete(Record).where(and_(*legacy_records_where)))
                await session.commit()
                print("Deleted legacy rows.")
            else:
                print("No legacy rows to delete.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
