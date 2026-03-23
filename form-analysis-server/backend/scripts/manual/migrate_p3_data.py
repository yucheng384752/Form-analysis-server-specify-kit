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
from app.models.p2_item import P2Item  # Import P2Item to resolve relationships

async def migrate_data():
    print("Starting P3 Item Product ID migration...")
    
    try:
        await database.init_db()
        
        async with database.async_session_factory() as session:
            # Fetch all P3 Items with their parent Records
            # We need to join Record to get production_date
            stmt = select(P3Item, Record).join(Record, P3Item.record_id == Record.id).where(Record.data_type == DataType.P3)
            result = await session.execute(stmt)
            rows = result.all()
            
            print(f"Found {len(rows)} P3 items to process.")
            
            updated_count = 0
            skipped_count = 0
            
            for p3_item, record in rows:
                # Extract components
                # 1. Date
                if not record.production_date:
                    print(f"Skipping Item {p3_item.id}: No production date in Record {record.id}")
                    skipped_count += 1
                    continue
                
                date_str = record.production_date.strftime('%Y%m%d')
                
                # 2. Machine
                machine = p3_item.machine_no
                if not machine:
                    # Fallback to Record's machine_no if item doesn't have it?
                    # User said "machine_no" from p3_items.
                    # If missing, maybe fallback to record?
                    machine = record.machine_no
                
                if not machine:
                    print(f"Skipping Item {p3_item.id}: No machine_no")
                    skipped_count += 1
                    continue
                    
                # 3. Mold
                mold = p3_item.mold_no
                if not mold:
                    mold = record.mold_no
                
                if not mold:
                    print(f"Skipping Item {p3_item.id}: No mold_no")
                    skipped_count += 1
                    continue
                    
                # 4. Lot
                # Try to get from row_data
                lot = None
                if p3_item.row_data:
                    lot = p3_item.row_data.get('lot') or p3_item.row_data.get('LOT') or p3_item.row_data.get('Lot')
                
                if not lot:
                    # Fallback to record's production_lot
                    lot = record.production_lot
                    
                if not lot:
                    print(f"Skipping Item {p3_item.id}: No lot found")
                    skipped_count += 1
                    continue
                
                # Construct Product ID
                # Format: YYYYMMDD_Machine_Mold_Lot
                base_product_id = f"{date_str}_{machine}_{mold}_{lot}"
                new_product_id = base_product_id
                
                # Check for duplicates in the current batch of updates
                # We need to track what we've assigned so far to avoid conflicts within the transaction
                # But checking against DB for every item is slow.
                # Since we are processing all items, we can track seen IDs.
                
                # Initialize seen_ids set outside the loop if not already
                if 'seen_ids' not in locals():
                    seen_ids = set()
                    # Pre-populate with existing IDs in DB? 
                    # Actually, we are updating ALL items that match P3.
                    # But there might be other items not loaded?
                    # For safety, let's just handle duplicates within the processed set first.
                    # If it conflicts with existing DB record that is NOT being updated, we'll hit integrity error.
                
                dup_count = 1
                while new_product_id in seen_ids:
                    new_product_id = f"{base_product_id}_{dup_count}"
                    dup_count += 1
                
                seen_ids.add(new_product_id)
                
                if p3_item.product_id != new_product_id:
                    print(f"Updating Item {p3_item.id} (Row {p3_item.row_no}): {p3_item.product_id} -> {new_product_id}")
                    p3_item.product_id = new_product_id
                    updated_count += 1
            
            if updated_count > 0:
                print(f"Committing {updated_count} changes...")
                await session.commit()
                print("Data migration completed.")
            else:
                print("No changes needed.")
                
    except Exception as e:
        print(f"Error during data migration: {e}")
        raise

async def drop_record_product_id():
    print("\nDropping product_id column from records table...")
    try:
        async with database.async_session_factory() as session:
            # Check if column exists first?
            # PostgreSQL: ALTER TABLE records DROP COLUMN IF EXISTS product_id;
            await session.execute(text("ALTER TABLE records DROP COLUMN IF EXISTS product_id"))
            await session.commit()
            print("Column dropped successfully.")
    except Exception as e:
        print(f"Error dropping column: {e}")

async def main():
    await migrate_data()
    await drop_record_product_id()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
