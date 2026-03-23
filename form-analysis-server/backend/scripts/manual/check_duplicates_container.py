import asyncio
import sys
import os
from sqlalchemy import select

# No need to modify sys.path if running from /app in container

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
        # Query for P2 records with lot_no = '2507173_02'
        stmt = select(Record).where(
            Record.data_type == DataType.P2,
            Record.lot_no == '2507173_02'
        ).order_by(Record.created_at)
        
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        print(f"Found {len(records)} P2 records for lot_no '2507173_02':")
        
        for r in records:
            rows = r.additional_data.get('rows', []) if r.additional_data and isinstance(r.additional_data, dict) else []
            rows_count = len(rows)
            print(f"ID: {r.id}, Winder: {r.winder_number}, Created: {r.created_at}, Additional Data Rows: {rows_count}")
            
            # Check for duplicate rows inside the record
            if rows_count > 0:
                # Convert rows to tuple of sorted items to make them hashable
                seen = set()
                duplicates = []
                for i, row in enumerate(rows):
                    # Create a hashable representation of the row
                    row_tuple = tuple(sorted((k, str(v)) for k, v in row.items()))
                    if row_tuple in seen:
                        duplicates.append(i)
                    else:
                        seen.add(row_tuple)
                
                if duplicates:
                    print(f"  WARNING: Found {len(duplicates)} duplicate rows inside this record!")
            
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
