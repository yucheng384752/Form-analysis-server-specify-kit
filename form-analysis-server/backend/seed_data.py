import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.append(str(Path(__file__).parent))

from app.core import database
from app.models.core.tenant import Tenant
from app.models.p1_record import P1Record
from sqlalchemy import select

async def seed():
    print("Initializing DB...")
    await database.init_db()
    
    async with database.async_session_factory() as session:
        # 1. Tenant
        print("Checking Tenant...")
        result = await session.execute(select(Tenant))
        tenant = result.scalars().first()
        if not tenant:
            print("Creating default tenant...")
            tenant = Tenant(name="Default Tenant", code="default", is_default=True)
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
        else:
            print(f"Tenant exists: {tenant.name} ({tenant.id})")
            
        # 2. P1 Record
        print("Checking P1 Record...")
        result = await session.execute(select(P1Record).limit(1))
        p1 = result.scalars().first()
        if not p1:
            print("Creating dummy P1 record...")
            p1 = P1Record(
                tenant_id=tenant.id,
                lot_no_raw="1234567-01",
                lot_no_norm=123456701,
                extras={
                    "product_name": "Test Product",
                    "quantity": 100,
                    "production_date": "2023-01-01"
                }
            )
            session.add(p1)
            await session.commit()
            print("P1 record created.")
        else:
            print(f"P1 record exists: {p1.id}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed())
