"""Bootstrap a tenant-bound API key.

安全定位：用於第一次上線前，在 DB 中建立第一把 API key。

規則（預設）：
- 僅允許在 tenant_api_keys 為 0 筆時建立（避免被用來無限制發 key）
- raw key 只會輸出一次（請自行保存）

用法（PowerShell）：
    Set-Location form-analysis-server
    python ./backend/scripts/bootstrap_tenant_api_key.py --label "admin" --tenant-code ut

環境變數：
- DATABASE_URL（會透過 app.core.config.Settings 讀 .env）
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, func

# Ensure `import app...` works when invoked from repo root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.core.database import Base, init_db
from app.core.auth import generate_api_key, hash_api_key
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey


async def _ensure_tables() -> None:
    await init_db()
    from app.core.database import engine

    if engine is None:
        raise RuntimeError("Database engine not initialized")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main_async(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a tenant-bound API key")
    parser.add_argument("--tenant-id", help="Target tenant UUID")
    parser.add_argument("--tenant-code", help="Target tenant code")
    parser.add_argument("--label", default="default", help="Key label")
    parser.add_argument("--force", action="store_true", help="Allow creating even if keys already exist")

    args = parser.parse_args(argv)

    settings = get_settings()
    await _ensure_tables()

    from app.core.database import async_session_factory

    if async_session_factory is None:
        raise RuntimeError("Database not initialized")

    async with async_session_factory() as db:
        # Safety gate
        key_count = (await db.execute(select(func.count(TenantApiKey.id)))).scalar() or 0
        if key_count > 0 and not args.force:
            raise RuntimeError(
                "Refuse to create API key because tenant_api_keys already has entries. "
                "Use --force if you really want to add another key."
            )

        # Resolve tenant
        tenant = None
        if args.tenant_id:
            try:
                tid = UUID(args.tenant_id)
            except ValueError as exc:
                raise RuntimeError("Invalid --tenant-id") from exc
            tenant = (await db.execute(select(Tenant).where(Tenant.id == tid))).scalar_one_or_none()
        elif args.tenant_code:
            tenant = (await db.execute(select(Tenant).where(Tenant.code == args.tenant_code))).scalar_one_or_none()
        else:
            # Best default: if only one tenant exists, use it; otherwise require explicit.
            tenants = (await db.execute(select(Tenant))).scalars().all()
            if len(tenants) == 1:
                tenant = tenants[0]

        if not tenant:
            raise RuntimeError(
                "Cannot resolve tenant. Provide --tenant-id or --tenant-code. "
                "(Or ensure only one tenant exists.)"
            )

        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)

        api_key = TenantApiKey(
            tenant_id=tenant.id,
            key_hash=key_hash,
            label=args.label,
            is_active=True,
        )
        db.add(api_key)
        await db.commit()

    # Output raw key ONCE
    sys.stdout.write("\n")
    sys.stdout.write("Bootstrap API key created\n")
    sys.stdout.write(f"tenant_id: {tenant.id}\n")
    sys.stdout.write(f"tenant_code: {tenant.code}\n")
    sys.stdout.write(f"label: {args.label}\n")
    sys.stdout.write("\n")
    sys.stdout.write("SAVE THIS KEY NOW (shown once):\n")
    sys.stdout.write(raw_key + "\n")
    sys.stdout.write("\n")

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async(sys.argv[1:])))


if __name__ == "__main__":
    main()
