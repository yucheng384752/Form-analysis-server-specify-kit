
import asyncio
import sys
import os

# Add the current directory to sys.path to make app module importable
sys.path.append(os.getcwd())

from app.core import database
from app.models.record import Record, DataType
from app.models.p2_item import P2Item
from app.models.p3_item import P3Item
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

async def check_p2_items():
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
        
        # Check additional_data['rows'] count
        rows_in_json = len(record.additional_data.get('rows', [])) if record.additional_data else 0
        print(f"Rows in additional_data: {rows_in_json}")
        
        # Check p2_items count
        p2_items_count = len(record.p2_items)
        print(f"Items in p2_items relationship: {p2_items_count}")
        
        # Check p2_items table directly
        stmt_count = select(func.count()).where(P2Item.record_id == record.id)
        result_count = await db.execute(stmt_count)
        db_count = result_count.scalar()
        print(f"Count in p2_items table: {db_count}")

        print("\nChecking winder number consistency:")
        mismatches = []
        for item in record.p2_items:
            row_winder = item.row_data.get('Winder number')
            # Handle string/int conversion
            try:
                row_winder_int = int(row_winder)
            except (ValueError, TypeError):
                row_winder_int = None
            
            if row_winder_int is not None and item.winder_number != row_winder_int:
                print(f"Mismatch! Item ID: {item.id}, DB Winder: {item.winder_number}, Row Data Winder: {row_winder_int}")
                mismatches.append(item.id)
            else:
                # print(f"Match: DB {item.winder_number} == Row {row_winder_int}")
                pass
                
        print(f"\nTotal mismatches found: {len(mismatches)}")


if __name__ == "__main__":
    asyncio.run(check_p2_items())
