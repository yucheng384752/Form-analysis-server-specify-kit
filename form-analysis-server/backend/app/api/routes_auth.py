from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.auth import generate_api_key, hash_api_key
from app.core.config import get_settings
from app.core.password import hash_password, verify_password
from app.models.core.tenant import Tenant
from app.models.core.tenant_api_key import TenantApiKey
from app.models.core.tenant_user import TenantUser

router = APIRouter()


class LoginRequest(BaseModel):
    tenant_code: Optional[str] = Field(default=None, description="Tenant code (場域代碼). If omitted, auto-resolves when exactly one tenant exists.")
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    tenant_id: str
    tenant_code: str
    api_key: str
    api_key_header: str

    model_config = ConfigDict(from_attributes=True)


class CreateUserRequest(BaseModel):
    tenant_code: Optional[str] = Field(default=None, description="Tenant code (場域代碼).")
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200, description="Minimum 8 characters")
    role: str = Field(default="user", min_length=1, max_length=30)


class CreateUserResponse(BaseModel):
    id: str
    tenant_id: str
    tenant_code: str
    username: str
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@router.post("/users", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    payload: CreateUserRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Create a tenant user.

    Allowed callers:
    - Break-glass bootstrap: valid ADMIN_API_KEYS (X-Admin-API-Key), can target any tenant by tenant_code.
    - Day-to-day: authenticated API key whose linked user has role=admin, can only create users in its own tenant.
    """

    settings = get_settings()
    admin_header = getattr(settings, "admin_api_key_header", "X-Admin-API-Key")
    admin_keys = getattr(settings, "admin_api_keys", set())

    provided = request.headers.get(admin_header)
    is_admin_key = bool(provided and provided.strip() in admin_keys)

    actor_role = getattr(getattr(request, "state", None), "actor_role", None)
    auth_tenant_id = getattr(getattr(request, "state", None), "auth_tenant_id", None)
    is_tenant_admin = bool(actor_role == "admin" and auth_tenant_id)

    if not is_admin_key and not is_tenant_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")

    tenant: Tenant | None = None
    if is_admin_key:
        tenant_code = (payload.tenant_code or "").strip() or None
        if tenant_code:
            tenant = (await db.execute(select(Tenant).where(Tenant.code == tenant_code, Tenant.is_active == True))).scalar_one_or_none()
            if not tenant:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown tenant_code")
        else:
            tenants = (await db.execute(select(Tenant).where(Tenant.is_active == True))).scalars().all()
            if len(tenants) != 1:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_code required when multiple tenants exist")
            tenant = tenants[0]
    else:
        # role=admin via API key: tenant is bound by middleware
        tenant = (await db.execute(select(Tenant).where(Tenant.id == auth_tenant_id, Tenant.is_active == True))).scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown tenant")

    username = payload.username.strip()
    existing = (
        await db.execute(
            select(TenantUser).where(TenantUser.tenant_id == tenant.id, TenantUser.username == username)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = TenantUser(
        tenant_id=tenant.id,
        username=username,
        password_hash=hash_password(payload.password),
        role=payload.role.strip() or "user",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return CreateUserResponse(
        id=str(user.id),
        tenant_id=str(tenant.id),
        tenant_code=str(tenant.code),
        username=user.username,
        role=user.role,
        is_active=bool(user.is_active),
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Password login to obtain an API key.

    Design:
    - Keeps existing X-API-Key auth for all business APIs.
    - This endpoint is exempted from AUTH_MODE=api_key middleware so users can log in.

    Security notes:
    - Returns raw api_key (token) to client; treat it as a session token.
    - Rotates the per-user key (revokes previous active key with same label).
    """

    tenant_code = (payload.tenant_code or "").strip() or None

    tenant: Tenant | None = None
    if tenant_code:
        tenant = (await db.execute(select(Tenant).where(Tenant.code == tenant_code, Tenant.is_active == True))).scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown tenant_code")
    else:
        tenants = (await db.execute(select(Tenant).where(Tenant.is_active == True))).scalars().all()
        if len(tenants) != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_code required when multiple tenants exist")
        tenant = tenants[0]

    username = payload.username.strip()
    user = (
        await db.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant.id,
                TenantUser.username == username,
                TenantUser.is_active == True,
            )
        )
    ).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    settings = get_settings()

    # Rotate per-user API key (one active key per username per tenant).
    label = f"login:{username}"
    await db.execute(
        update(TenantApiKey)
        .where(TenantApiKey.tenant_id == tenant.id, TenantApiKey.label == label, TenantApiKey.is_active == True)
        .values(is_active=False, revoked_at=func.now())
    )

    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key=raw_key, secret_key=settings.secret_key)

    api_key_row = TenantApiKey(
        tenant_id=tenant.id,
        key_hash=key_hash,
        label=label,
        is_active=True,
        user_id=user.id,
    )
    db.add(api_key_row)

    # Best-effort last_login tracking.
    try:
        user.last_login_at = func.now()
    except Exception:
        pass

    await db.commit()

    header_name = getattr(settings, "auth_api_key_header", "X-API-Key")
    return LoginResponse(
        tenant_id=str(tenant.id),
        tenant_code=str(tenant.code),
        api_key=raw_key,
        api_key_header=header_name,
    )
