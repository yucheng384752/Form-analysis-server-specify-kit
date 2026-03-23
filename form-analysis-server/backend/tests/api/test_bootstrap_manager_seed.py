import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.bootstrap import bootstrap_manager_user_if_configured
from app.models.core.tenant import Tenant
from app.models.core.tenant_user import TenantUser


@pytest.mark.asyncio
async def test_bootstrap_manager_creates_user(db_session_clean, test_engine):
    tenant = Tenant(
        name=f"Test Tenant {uuid.uuid4()}",
        code="t1",
        is_default=True,
        is_active=True,
    )
    db_session_clean.add(tenant)
    await db_session_clean.commit()
    await db_session_clean.refresh(tenant)

    settings = SimpleNamespace(
        bootstrap_manager_enabled=True,
        bootstrap_manager_tenant_code="t1",
        bootstrap_manager_username="mgr",
        bootstrap_manager_password="password123",
        bootstrap_manager_must_change_password=False,
    )

    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    result = await bootstrap_manager_user_if_configured(
        async_session_factory=session_factory,
        settings=settings,
    )
    assert result.attempted is True
    assert result.created is True

    user = (
        await db_session_clean.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant.id,
                TenantUser.username == "mgr",
            )
        )
    ).scalar_one()
    assert user.role == "manager"
