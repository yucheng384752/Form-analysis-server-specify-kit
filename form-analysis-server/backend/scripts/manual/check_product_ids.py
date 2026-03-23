import asyncio
import sys
import os

# Set DATABASE_URL explicitly for the script to connect to the exposed port
os.environ["DATABASE_URL"] = "postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db"

print("Script started...")
from sqlalchemy import select

# Add the current directory to sys.path to make app imports work
sys.path.append(os.getcwd())

from app.core import database
from app.models.record import Record, DataType
# Import other models to resolve relationships
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item

async def main():
    try:
        await database.init_db()
    except Exception as e:
        print(f"Error initializing DB: {e}")
        # If init_db fails, it might be because we are not in the right environment or config is missing.
        # But let's try to proceed if session factory works.
        pass

    target_lot_no = '2507173_02'
    print(f"Checking for P3 records with Lot No: {target_lot_no}")

    try:
        async with database.async_session_factory() as session:
            # Query for P3 records with the specific lot_no
            stmt = select(Record).where(
                Record.lot_no == target_lot_no,
                Record.data_type == DataType.P3
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

            if not records:
                print(f"No P3 records found for Lot No: {target_lot_no}")
            else:
                print(f"Found {len(records)} P3 records:")
                for r in records:
                    print(f"\nFound Record:")
                    print(f"  ID: {r.id}")
                    print(f"  Product ID: {r.product_id}")
                    print(f"  Lot No: {r.lot_no}")
                    print(f"  Data Type: {r.data_type}")
                    print(f"  Machine No: {r.machine_no}")
                    print(f"  Mold No: {r.mold_no}")
                    print(f"  Production Lot: {r.production_lot}")
                    print(f"  Production Date: {r.production_date}")
                    
                    # Query P3 Items for this record
                    print(f"\n  Querying P3 Items for Record ID: {r.id}...")
                    stmt_items = select(P3Item).where(P3Item.record_id == r.id).order_by(P3Item.row_no)
                    result_items = await session.execute(stmt_items)
                    items = result_items.scalars().all()
                    
                    if not items:
                        print(f"  No P3 Items found for this record.")
                    else:
                        print(f"  Found {len(items)} P3 Items:")
                        for item in items:
                            # Check row_data for P3_No. and lot
                            p3_no = item.row_data.get('P3_No.') or item.row_data.get('P3 No.') or item.row_data.get('p3_no') or "N/A"
                            lot_val = item.row_data.get('lot') or item.row_data.get('LOT') or item.row_data.get('Lot') or "N/A"
                            print(f"    [Row {item.row_no}] Machine: {item.machine_no} | Mold: {item.mold_no} | Lot (row_data): {lot_val} | P3_No: {p3_no}")
                    
    except Exception as e:
        print(f"An error occurred during query: {e}")

if __name__ == "__main__":
    # Fix for Windows SelectorEventLoopPolicy
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
