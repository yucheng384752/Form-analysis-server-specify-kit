from typing import Optional
from fastapi import Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tenant_resolver import resolve_tenant_or_raise
from app.models.core.tenant import Tenant

async def get_current_tenant(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    """
    Resolve current tenant from Header or Default.
    
    Logic:
    1. If X-Tenant-Id header is present, use it to find tenant.
    2. If header is missing:
       - If only 1 tenant exists in DB, use it.
       - If multiple tenants exist, check for is_default=True.
       - If exactly one default tenant exists, use it.
       - Otherwise, raise 422 error requiring explicit tenant ID.
    """
    return await resolve_tenant_or_raise(db=db, x_tenant_id=x_tenant_id)
