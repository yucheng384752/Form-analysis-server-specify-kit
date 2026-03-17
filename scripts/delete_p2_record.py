
import sys
import os
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Determine the absolute path to the backend directory
script_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.dirname(script_dir)
backend_dir = os.path.join(workspace_root, 'form-analysis-server', 'backend')

if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Load DATABASE_URL from environment or .env file
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    from dotenv import load_dotenv
    env_path = os.path.join(workspace_root, "form-analysis-server", ".env")
    load_dotenv(env_path)
    DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is not set.")
    print("Set it directly or create form-analysis-server/.env with DATABASE_URL=...")
    sys.exit(1)

from app.models.record import Record, DataType
from app.models.p2_item import P2Item
from app.models.p3_item import P3Item

async def delete_record(lot_no):
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        print(f"Searching for P2 record with lot_no: {lot_no}...")
        
        # Find the record
        stmt = select(Record).where(Record.lot_no == lot_no).where(Record.data_type == DataType.P2)
        result = await db.execute(stmt)
        records = result.scalars().all()
        
        if not records:
            print(f"No P2 record found for lot_no: {lot_no}")
            return

        print(f"Found {len(records)} records.")
        
        for record in records:
            print(f"   🗑️ Deleting Record ID: {record.id}, Created: {record.created_at}")
            await db.delete(record)
        
        print(f"\n💾 Committing changes...")
        await db.commit()
        print(" Deletion complete.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(delete_record('2503033_97'))
