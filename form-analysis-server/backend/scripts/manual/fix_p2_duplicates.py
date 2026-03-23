
import asyncio
import sys
import os

# Add the current directory to sys.path to make app module importable
sys.path.append(os.getcwd())

from app.core import database
from app.models.record import Record, DataType
from app.models.p2_item import P2Item
from app.models.p3_item import P3Item
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

async def fix_p2_duplicates():
    await database.init_db()
    async with database.async_session_factory() as db:
        # Find the P2 record
        stmt = select(Record).where(
            Record.lot_no == '2507173_02',
            Record.data_type == DataType.P2
        ).options(selectinload(Record.p2_items))
        
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        
        if not record:
            print("Record not found")
            return

        print(f"Record ID: {record.id}")
        print(f"Lot No: {record.lot_no}")
        
        print("\nChecking for duplicates based on winder number mismatch...")
        items_to_delete = []
        
        for item in record.p2_items:
            row_winder = item.row_data.get('Winder number')
            try:
                row_winder_int = int(row_winder)
            except (ValueError, TypeError):
                row_winder_int = None
            
            if row_winder_int is not None and item.winder_number != row_winder_int:
                print(f"Mismatch found! Item ID: {item.id}, DB Winder: {item.winder_number}, Row Data Winder: {row_winder_int}")
                items_to_delete.append(item.id)
        
        if items_to_delete:
            print(f"\nDeleting {len(items_to_delete)} duplicate items...")
            delete_stmt = delete(P2Item).where(P2Item.id.in_(items_to_delete))
            await db.execute(delete_stmt)
            await db.commit()
            print("Deletion complete.")
        else:
            print("No duplicates found.")

if __name__ == "__main__":
    asyncio.run(fix_p2_duplicates())
