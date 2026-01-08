import asyncio
import sys
import uuid
from pathlib import Path

# Add project root to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from app.core import database
from app.models.core.schema_registry import TableRegistry
# Import models to ensure they are registered
from app.models.record import Record
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item
from sqlalchemy import select

async def seed_tables():
    await database.init_db()
    
    async with database.async_session_factory() as db:
        # Check if P3 exists
        result = await db.execute(select(TableRegistry).where(TableRegistry.table_code == "P3"))
        table = result.scalars().first()
        
        if table:
            print(f"Table P3 already exists: {table.id}")
        else:
            new_table = TableRegistry(
                id=uuid.uuid4(),
                table_code="P3",
                display_name="P3 Tracking Data"
            )
            db.add(new_table)
            await db.commit()
            print(f"Created table P3: {new_table.id}")

        # Check if P1 exists (for completeness)
        result = await db.execute(select(TableRegistry).where(TableRegistry.table_code == "P1"))
        table = result.scalars().first()
        
        if table:
            print(f"Table P1 already exists: {table.id}")
        else:
            new_table = TableRegistry(
                id=uuid.uuid4(),
                table_code="P1",
                display_name="P1 Product Data"
            )
            db.add(new_table)
            await db.commit()
            print(f"Created table P1: {new_table.id}")

if __name__ == "__main__":
    asyncio.run(seed_tables())
