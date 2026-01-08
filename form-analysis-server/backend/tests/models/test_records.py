import pytest
import uuid
from sqlalchemy.exc import IntegrityError
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record

@pytest.mark.asyncio
async def test_p1_record_creation(db_session, clean_db):
    # Create Tenant
    tenant = Tenant(name="Test Tenant P1", code="test_tenant_p1", is_default=True)
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    # Create P1 Record
    p1 = P1Record(
        tenant_id=tenant.id,
        lot_no_raw="1234567-01",
        lot_no_norm=123456701,
        extras={"some": "data"}
    )
    db_session.add(p1)
    await db_session.commit()
    await db_session.refresh(p1)

    assert p1.id is not None
    assert p1.tenant_id == tenant.id
    assert p1.lot_no_norm == 123456701

@pytest.mark.asyncio
async def test_p1_unique_constraint(db_session, clean_db):
    tenant = Tenant(name="Test Tenant P1 Unique", code="test_tenant_p1_unique")
    db_session.add(tenant)
    await db_session.commit()

    p1_a = P1Record(tenant_id=tenant.id, lot_no_raw="A", lot_no_norm=100)
    db_session.add(p1_a)
    await db_session.commit()

    p1_b = P1Record(tenant_id=tenant.id, lot_no_raw="B", lot_no_norm=100)
    db_session.add(p1_b)
    
    with pytest.raises(IntegrityError):
        await db_session.commit()
    
    await db_session.rollback()

@pytest.mark.asyncio
async def test_p2_record_creation(db_session, clean_db):
    tenant = Tenant(name="Test Tenant P2", code="test_tenant_p2")
    db_session.add(tenant)
    await db_session.commit()

    p2 = P2Record(
        tenant_id=tenant.id,
        lot_no_raw="1234567-02",
        lot_no_norm=123456702,
        winder_number=1,
        extras={}
    )
    db_session.add(p2)
    await db_session.commit()
    
    assert p2.winder_number == 1

@pytest.mark.asyncio
async def test_p3_record_creation(db_session, clean_db):
    tenant = Tenant(name="Test Tenant P3", code="test_tenant_p3")
    db_session.add(tenant)
    await db_session.commit()

    p3 = P3Record(
        tenant_id=tenant.id,
        lot_no_raw="1234567-03",
        lot_no_norm=123456703,
        production_date_yyyymmdd=20230101,
        machine_no="M1",
        mold_no="Mold1",
        extras={}
    )
    db_session.add(p3)
    await db_session.commit()
    
    assert p3.production_date_yyyymmdd == 20230101
