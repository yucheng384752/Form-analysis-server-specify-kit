import asyncio
import sys
import os
from sqlalchemy import select, text

# Set DATABASE_URL explicitly
os.environ["DATABASE_URL"] = "postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db"

# Add current directory to sys.path
sys.path.append(os.getcwd())

from app.core import database
from app.models.record import Record, DataType
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item

async def check_and_fill_p3_items():
    print("Checking P3 Items for missing fields (Machine, Mold, Lot) before dropping Record columns...")
    
    try:
        await database.init_db()
        
        async with database.async_session_factory() as session:
            # Fetch all P3 Items with Record
            stmt = select(P3Item, Record).join(Record, P3Item.record_id == Record.id).where(Record.data_type == DataType.P3)
            result = await session.execute(stmt)
            rows = result.all()
            
            updated_count = 0
            
            for p3_item, record in rows:
                needs_update = False
                
                # Machine
                if not p3_item.machine_no and record.machine_no:
                    print(f"Item {p3_item.id}: Copying Machine '{record.machine_no}' from Record")
                    p3_item.machine_no = record.machine_no
                    needs_update = True
                
                # Mold
                if not p3_item.mold_no and record.mold_no:
                    print(f"Item {p3_item.id}: Copying Mold '{record.mold_no}' from Record")
                    p3_item.mold_no = record.mold_no
                    needs_update = True
                    
                # Lot
                if not p3_item.lot_no and record.production_lot is not None:
                    print(f"Item {p3_item.id}: Copying Lot '{record.production_lot}' from Record")
                    p3_item.lot_no = str(record.production_lot)
                    needs_update = True
                
                if needs_update:
                    updated_count += 1
            
            if updated_count > 0:
                print(f"Updating {updated_count} items...")
                await session.commit()
                print("P3 Items backfill completed.")
            else:
                print("All P3 Items already have data. No backfill needed.")

    except Exception as e:
        print(f"Error: {e}")

async def drop_record_columns():
    print("\nDropping columns from records table: machine_no, mold_no, production_lot, product_id...")
    
    columns_to_drop = [
        "machine_no",
        "mold_no",
        "production_lot",
        "product_id" # Ensure this is gone too as requested
    ]
    
    try:
        async with database.async_session_factory() as session:
            for col in columns_to_drop:
                print(f"Dropping column: {col}")
                # Use IF EXISTS to be safe
                await session.execute(text(f"ALTER TABLE records DROP COLUMN IF EXISTS {col}"))
            
            await session.commit()
            print("Columns dropped successfully.")
            
    except Exception as e:
        print(f"Error dropping columns: {e}")

async def main():
    await check_and_fill_p3_items()
    await drop_record_columns()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
