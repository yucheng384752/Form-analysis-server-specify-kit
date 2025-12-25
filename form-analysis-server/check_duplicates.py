import asyncio
import sys
import os
from sqlalchemy import select

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import init_db, async_session_factory
from app.models.record import Record, DataType

async def main():
    try:
        await init_db()
    except Exception as e:
        print(f"Error initializing DB: {e}")
        return

    async with async_session_factory() as session:
        # Query for P2 records with lot_no = '2507173_02'
        stmt = select(Record).where(
            Record.data_type == DataType.P2,
            Record.lot_no == '2507173_02'
        ).order_by(Record.created_at)
        
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        print(f"Found {len(records)} P2 records for lot_no '2507173_02':")
        
        for r in records:
            rows_count = len(r.additional_data.get('rows', [])) if r.additional_data and isinstance(r.additional_data, dict) else 'None'
            print(f"ID: {r.id}, Winder: {r.winder_number}, Created: {r.created_at}, Additional Data Rows: {rows_count}")
            
        if len(records) > 1:
            print("\nDuplicates found!")
            print("SQL to delete duplicates (keeping the latest one):")
            
            # Keep the last one (latest created_at)
            keep_id = records[-1].id
            delete_ids = [str(r.id) for r in records[:-1]]
            
            ids_str = "', '".join(delete_ids)
            print(f"DELETE FROM records WHERE id IN ('{ids_str}');")
        else:
            print("\nNo duplicates found.")

if __name__ == "__main__":
    asyncio.run(main())
