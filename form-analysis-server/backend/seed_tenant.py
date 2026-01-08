import asyncio
import sys
import uuid
from pathlib import Path

# Add project root to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from app.core import database
from app.models.core.tenant import Tenant
# Import models to ensure they are registered
from app.models.record import Record
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item
from sqlalchemy import select

async def seed_tenant():
    print("Initializing DB...")
    await database.init_db()
    print(f"Factory: {database.async_session_factory}")
    
    async with database.async_session_factory() as db:
        # Check if tenant exists
        result = await db.execute(select(Tenant))
        tenant = result.scalars().first()
        
        if tenant:
            print(f"Tenant already exists: {tenant.name} ({tenant.id})")
            return
        
        # Create default tenant
        new_tenant = Tenant(
            id=uuid.uuid4(),
            name="Default Tenant",
            code="DEFAULT",
            is_active=True
        )
        db.add(new_tenant)
        await db.commit()
        print(f"Created default tenant: {new_tenant.name} ({new_tenant.id})")

if __name__ == "__main__":
    asyncio.run(seed_tenant())
