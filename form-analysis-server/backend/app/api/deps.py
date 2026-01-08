from typing import Optional
from uuid import UUID
from fastapi import Header, HTTPException, Depends, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
    # 1. If Header is provided, verify it
    if x_tenant_id:
        try:
            tenant_uuid = UUID(x_tenant_id)
        except ValueError:
             raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid X-Tenant-Id format")
        
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return tenant

    # 2. If Header is NOT provided, try to resolve default
    # Check total count
    count_result = await db.execute(select(func.count(Tenant.id)))
    total_count = count_result.scalar()

    if total_count == 1:
        # Only 1 tenant exists, return it
        result = await db.execute(select(Tenant))
        return result.scalar_one()
    
    # Check for default tenant
    result = await db.execute(select(Tenant).where(Tenant.is_default == True))
    default_tenants = result.scalars().all()
    
    if len(default_tenants) == 1:
        return default_tenants[0]
    
    # Cannot resolve automatically
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
        detail="X-Tenant-Id header is required (Multiple tenants exist and no unique default)"
    )
