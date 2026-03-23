from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root (/app) is importable when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select, update

from app.core import database
from app.core.auth import generate_api_key, hash_api_key
from app.core.config import get_settings
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey
from app.models.core.tenant_user import TenantUser  # noqa: F401


async def main() -> None:
    await database.init_db()
    settings = get_settings()

    if database.async_session_factory is None:
        raise RuntimeError("Database not initialized (async_session_factory is None)")

    async with database.async_session_factory() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.code == "default", Tenant.is_active == True))
        ).scalar_one()

        label = "debug:copilot"

        await db.execute(
            update(TenantApiKey)
            .where(
                TenantApiKey.tenant_id == tenant.id,
                TenantApiKey.label == label,
                TenantApiKey.is_active == True,
            )
            .values(is_active=False, revoked_at=func.now())
        )

        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)

        db.add(
            TenantApiKey(
                tenant_id=tenant.id,
                key_hash=key_hash,
                label=label,
                is_active=True,
                user_id=None,
            )
        )
        await db.commit()

    print(f"TENANT_ID={tenant.id}")
    print(f"API_KEY_HEADER={getattr(settings, 'auth_api_key_header', 'X-API-Key')}")
    print(f"API_KEY={raw_key}")


if __name__ == "__main__":
    asyncio.run(main())
