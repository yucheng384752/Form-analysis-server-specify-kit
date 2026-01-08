import pytest
from fastapi import HTTPException
from app.api.deps import get_current_tenant
from app.models.core.tenant import Tenant

@pytest.mark.asyncio
async def test_get_current_tenant_with_header(db_session, clean_db):
    # Setup
    tenant = Tenant(name="Header Tenant", code="header_tenant")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    
    # Test
    result = await get_current_tenant(x_tenant_id=str(tenant.id), db=db_session)
    assert result.id == tenant.id

@pytest.mark.asyncio
async def test_get_current_tenant_single_existing(db_session, clean_db):
    # Setup
    tenant = Tenant(name="Single Tenant", code="single_tenant")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    
    # Test
    result = await get_current_tenant(x_tenant_id=None, db=db_session)
    assert result.id == tenant.id

@pytest.mark.asyncio
async def test_get_current_tenant_default(db_session, clean_db):
    # Setup
    t1 = Tenant(name="T1", code="t1")
    t2 = Tenant(name="T2", code="t2", is_default=True)
    db_session.add_all([t1, t2])
    await db_session.commit()
    await db_session.refresh(t2)
    
    # Test
    result = await get_current_tenant(x_tenant_id=None, db=db_session)
    assert result.id == t2.id

@pytest.mark.asyncio
async def test_get_current_tenant_fail_multiple_no_default(db_session, clean_db):
    # Setup
    t1 = Tenant(name="T1", code="t1")
    t2 = Tenant(name="T2", code="t2")
    db_session.add_all([t1, t2])
    await db_session.commit()
    
    # Test
    with pytest.raises(HTTPException) as exc:
        await get_current_tenant(x_tenant_id=None, db=db_session)
    assert exc.value.status_code == 422

@pytest.mark.asyncio
async def test_get_current_tenant_invalid_header(db_session, clean_db):
    with pytest.raises(HTTPException) as exc:
        await get_current_tenant(x_tenant_id="invalid-uuid", db=db_session)
    assert exc.value.status_code == 422

@pytest.mark.asyncio
async def test_get_current_tenant_not_found(db_session, clean_db):
    import uuid
    random_uuid = str(uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        await get_current_tenant(x_tenant_id=random_uuid, db=db_session)
    assert exc.value.status_code == 404
