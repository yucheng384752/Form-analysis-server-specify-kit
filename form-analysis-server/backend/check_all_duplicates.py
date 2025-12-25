import asyncio
import sys
import os
from sqlalchemy import select

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
        lot_no = '2507173_02'
        print(f"Checking ALL records for Lot No: {lot_no}")
        
        stmt = select(Record).where(Record.lot_no == lot_no).order_by(Record.data_type, Record.created_at)
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        if not records:
            print("No records found.")
            return

        by_type = {'P1': [], 'P2': [], 'P3': []}
        for r in records:
            if r.data_type:
                by_type[r.data_type.value].append(r)
            else:
                print(f"Warning: Record {r.id} has no data_type")

        for dtype, recs in by_type.items():
            print(f"\n--- {dtype} Records ({len(recs)}) ---")
            for r in recs:
                rows = r.additional_data.get('rows', []) if r.additional_data and isinstance(r.additional_data, dict) else []
                rows_count = len(rows)
                print(f"ID: {r.id}")
                print(f"  Created: {r.created_at}")
                print(f"  Winder: {r.winder_number}")
                print(f"  Product ID: {r.product_id}")
                print(f"  Rows count: {rows_count}")
                
                # Check for duplicate rows inside
                if rows_count > 0:
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

            if len(recs) > 1:
                print(f"  !! POTENTIAL DUPLICATE RECORDS FOUND for {dtype} !!")
                print("  SQL to delete duplicates (keeping the latest one):")
                keep_id = recs[-1].id
                delete_ids = [str(r.id) for r in recs[:-1]]
                ids_str = "', '".join(delete_ids)
                print(f"  DELETE FROM records WHERE id IN ('{ids_str}');")

if __name__ == "__main__":
    asyncio.run(main())
