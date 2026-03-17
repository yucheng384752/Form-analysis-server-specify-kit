from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_request_state_attr
from app.core.config import get_settings
from app.core.database import get_db
from app.models.core.audit_event import AuditEvent
from app.models.core.tenant import Tenant
from app.schemas.audit_event import AuditEventResponse

router = APIRouter(tags=["Audit Events"])


@router.get("/api/audit-events", response_model=list[AuditEventResponse])
async def list_audit_events(
    request: Request,
    action: str | None = Query(None, description="Filter by action"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """List audit events for the current tenant."""

    stmt = select(AuditEvent).where(AuditEvent.tenant_id == current_tenant.id)
    if action and action.strip():
        stmt = stmt.where(AuditEvent.action == action.strip())

    stmt = stmt.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/api/admin/audit-events", response_model=list[AuditEventResponse])
async def admin_list_audit_events(
    request: Request,
    tenant_id: UUID | None = Query(None, description="Optional tenant filter"),
    action: str | None = Query(None, description="Filter by action"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Admin: list audit events across tenants (optionally filtered)."""

    settings = get_settings()
    admin_header = getattr(settings, "admin_api_key_header", "X-Admin-API-Key")
    admin_keys = getattr(settings, "admin_api_keys", set())

    is_admin_state = bool(get_request_state_attr(request, "is_admin", False))
    provided = request.headers.get(admin_header)
    is_admin_key = bool(provided and provided.strip() in admin_keys)
    if not (is_admin_state or is_admin_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin API key required"
        )

    stmt = select(AuditEvent)
    if tenant_id is not None:
        stmt = stmt.where(AuditEvent.tenant_id == tenant_id)
    if action and action.strip():
        stmt = stmt.where(AuditEvent.action == action.strip())

    stmt = stmt.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
