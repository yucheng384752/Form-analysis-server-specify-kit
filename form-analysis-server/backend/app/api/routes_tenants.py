from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings
from app.models.core.tenant import Tenant

router = APIRouter(tags=["Tenants"])

class TenantResponse(BaseModel):
    id: UUID
    name: str
    code: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

@router.get("/api/tenants", response_model=List[TenantResponse])
async def get_tenants(request: Request, db: AsyncSession = Depends(get_db)):
    """
    取得所有 Tenant 列表。
    前端根據回傳數量決定是否顯示選擇器。
    """
    is_admin = bool(getattr(getattr(request, "state", None), "is_admin", False))
    auth_tenant_id = getattr(getattr(request, "state", None), "auth_tenant_id", None)

    stmt = select(Tenant).where(Tenant.is_active == True)
    if not is_admin and auth_tenant_id:
        stmt = stmt.where(Tenant.id == auth_tenant_id)

    result = await db.execute(stmt)
    return result.scalars().all()


class TenantCreateRequest(BaseModel):
    """Create a tenant.

    Used by UI bootstrap when no tenants exist.
    """

    name: str = Field(default="UT", min_length=1, max_length=100)
    code: str = Field(default="ut", min_length=1, max_length=50)
    is_active: bool = True
    is_default: bool = True


@router.post("/api/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreateRequest = Body(default_factory=TenantCreateRequest),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a tenant.

    Safety:
    - Will not delete/reset any data.
    - If a tenant already exists, returns 409 to avoid surprising mutations.
    """

    settings = get_settings()
    admin_header = getattr(settings, "admin_api_key_header", "X-Admin-API-Key")
    admin_keys = getattr(settings, "admin_api_keys", set())

    is_admin = bool(getattr(getattr(request, "state", None), "is_admin", False)) if request is not None else False
    provided = request.headers.get(admin_header) if request is not None else None
    if not is_admin and not (provided and provided.strip() in admin_keys):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin API key required")

    tenant_count = (await db.execute(select(func.count(Tenant.id)))).scalar() or 0
    if tenant_count > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant already exists")

    tenant = Tenant(
        name=payload.name,
        code=payload.code,
        is_default=payload.is_default,
        is_active=payload.is_active,
    )

    db.add(tenant)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Another request may have created it concurrently.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant already exists")

    await db.refresh(tenant)
    return tenant
