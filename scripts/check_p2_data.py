import asyncio
import sys
import os

# Add backend directory to python path
sys.path.append(os.path.join(os.getcwd(), 'form-analysis-server', 'backend'))

from app.core.database import init_db, async_session_factory
from app.models.record import Record, DataType
from app.models.p2_item import P2Item
from app.models.p3_item import P3Item
from sqlalchemy import select

async def check_p2_records():
    await init_db()
    from app.core.database import async_session_factory
    async with async_session_factory() as session:
        # List some P2 records to see the lot_no format
        stmt = select(Record).where(Record.data_type == DataType.P2).limit(10)
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        print(f"Found {len(records)} P2 records.")
        for r in records:
            print(f"ID: {r.id}, Lot: {r.lot_no}, Winder: {r.winder_number}")

        # Check specifically for 2507173_02
        print("\nChecking for Lot: 2507173_02")
        # Check specific lot
        target_lot = "2507173_02"
        print(f"\nChecking for Lot: {target_lot}")
        
        stmt = select(Record).where(
            Record.data_type == DataType.P2,
            Record.lot_no == target_lot
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        print(f"Found {len(records)} P2 records with lot_no='{target_lot}'")
        for r in records:
            print(f"  - ID: {r.id}, Winder: {r.winder_number}")

        # Check P3 records for this lot
        stmt_p3 = select(Record).where(
            Record.data_type == DataType.P3,
            Record.lot_no == target_lot
        )
        result_p3 = await session.execute(stmt_p3)
        records_p3 = result_p3.scalars().all()
        
        print(f"Found {len(records_p3)} P3 records with lot_no='{target_lot}'")
        for r in records_p3:
            print(f"  - ID: {r.id}")
            print(f"    Product ID: {r.product_id}")
            print(f"    Lot No: {r.lot_no}")
            print(f"    Source Winder: {r.source_winder}")
            print(f"    Additional Data: {r.additional_data}")

if __name__ == "__main__":
    asyncio.run(check_p2_records())
