from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.core.tenant import Tenant
from pydantic import BaseModel

router = APIRouter(tags=["Tenants"])

class TenantResponse(BaseModel):
    id: UUID
    name: str
    code: str
    is_active: bool

    class Config:
        from_attributes = True

@router.get("/api/tenants", response_model=List[TenantResponse])
async def get_tenants(db: AsyncSession = Depends(get_db)):
    """
    取得所有 Tenant 列表。
    前端根據回傳數量決定是否顯示選擇器。
    """
    result = await db.execute(select(Tenant).where(Tenant.is_active == True))
    tenants = result.scalars().all()
    return tenants
