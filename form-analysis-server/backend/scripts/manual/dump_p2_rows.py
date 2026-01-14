import asyncio
import json
from sqlalchemy import select, text

from app.core import database
from app.models.record import Record, DataType
# Import other models to ensure relationships are resolved
from app.models.p2_item import P2Item
from app.models.p3_item import P3Item

async def main():
    try:
        await database.init_db()
    except Exception as e:
        print(f"Error initializing DB: {e}")
        return

    async with database.async_session_factory() as session:
        # Search for anything resembling the lot no
        print("Searching for records with lot_no like '2507173_02'...")
        stmt = select(Record).where(Record.lot_no.ilike('%2507173_02%'))
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        print(f"Found {len(records)} records.")
        
        for r in records:
            print(f"\nID: {r.id}")
            print(f"Type: {r.data_type}")
            print(f"Lot No: '{r.lot_no}'")
            
            if r.data_type == DataType.P2:
                rows = r.additional_data.get('rows', []) if r.additional_data else []
                print(f"Rows count: {len(rows)}")
                
                # Dump rows to file for inspection
                filename = f"p2_dump_{r.lot_no}_{r.id}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(rows, f, ensure_ascii=False, indent=2)
                print(f"Dumped rows to {filename}")

if __name__ == "__main__":
    asyncio.run(main())
