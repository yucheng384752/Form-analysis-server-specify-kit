import asyncio
import sys
import os
from collections import defaultdict
from sqlalchemy import select, delete

# Set DATABASE_URL explicitly
os.environ["DATABASE_URL"] = "postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db"

# Add current directory to sys.path
sys.path.append(os.getcwd())

from app.core import database
from app.models.record import Record, DataType
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item  # Required for Record relationships

async def cleanup_p3_items():
    print("Starting P3 Items cleanup and validation...")
    
    try:
        await database.init_db()
        
        async with database.async_session_factory() as session:
            # Fetch all P3 Items with their parent Records
            stmt = select(P3Item, Record).join(Record, P3Item.record_id == Record.id).where(Record.data_type == DataType.P3)
            result = await session.execute(stmt)
            rows = result.all()
            
            print(f"Total P3 items found: {len(rows)}")
            
            items_by_expected_id = defaultdict(list)
            non_conforming_list = []
            
            # 1. Group items by their EXPECTED product_id
            for p3_item, record in rows:
                # Construct Expected ID
                if not record.production_date:
                    print(f"Warning: Item {p3_item.id} has no production date. Skipping.")
                    continue
                    
                date_str = record.production_date.strftime('%Y%m%d')
                
                # Use item fields, fallback to record fields
                machine = p3_item.machine_no or record.machine_no
                mold = p3_item.mold_no or record.mold_no
                
                # Lot from row_data or record
                lot = None
                if p3_item.row_data:
                    lot = p3_item.row_data.get('lot') or p3_item.row_data.get('LOT') or p3_item.row_data.get('Lot')
                if not lot:
                    lot = record.production_lot
                
                if not (machine and mold and lot):
                    print(f"Warning: Item {p3_item.id} missing components for ID generation. Machine:{machine}, Mold:{mold}, Lot:{lot}")
                    continue
                
                # Clean strings
                machine = str(machine).strip()
                mold = str(mold).strip()
                lot = str(lot).strip()
                
                expected_id = f"{date_str}-{machine}-{mold}-{lot}"
                
                # Check if current ID matches expected
                if p3_item.product_id != expected_id:
                    non_conforming_list.append({
                        "id": str(p3_item.id),
                        "current": p3_item.product_id,
                        "expected": expected_id,
                        "reason": "Mismatch" if p3_item.product_id and not p3_item.product_id.startswith(expected_id) else "Duplicate/Suffix"
                    })
                
                items_by_expected_id[expected_id].append(p3_item)

            # 2. Identify Duplicates and Updates
            to_delete = []
            to_update = []
            
            print("\n--- Analysis Report ---")
            print(f"Unique Expected IDs: {len(items_by_expected_id)}")
            
            for expected_id, group in items_by_expected_id.items():
                # Sort by row_no to keep the first occurrence (assuming lower row_no is the 'original')
                group.sort(key=lambda x: x.row_no)
                
                keeper = group[0]
                duplicates = group[1:]
                
                if duplicates:
                    print(f"Duplicate Group for {expected_id}: {len(group)} items")
                    for dup in duplicates:
                        print(f"  - Marking for deletion: {dup.id} (Current ID: {dup.product_id})")
                        to_delete.append(dup)
                
                if keeper.product_id != expected_id:
                    print(f"  - Marking for update: {keeper.id} (Current: {keeper.product_id} -> Expected: {expected_id})")
                    to_update.append((keeper, expected_id))

            # 3. Execute Changes
            if to_delete:
                print(f"\nDeleting {len(to_delete)} duplicate items...")
                delete_ids = [item.id for item in to_delete]
                # Bulk delete
                await session.execute(delete(P3Item).where(P3Item.id.in_(delete_ids)))
            
            if to_update:
                print(f"Updating {len(to_update)} items to correct Product ID...")
                for item, new_id in to_update:
                    item.product_id = new_id
                    # We don't need to add to session, it's already attached
            
            if to_delete or to_update:
                await session.commit()
                print("\nCleanup completed successfully.")
            else:
                print("\nNo changes needed.")

            # 4. Print Non-Conforming List (Original state)
            if non_conforming_list:
                print("\n--- Non-Conforming Product IDs (Before Cleanup) ---")
                for item in non_conforming_list:
                    print(f"ID: {item['id']} | Current: {item['current']} | Expected: {item['expected']} | Reason: {item['reason']}")
            else:
                print("\nAll items were already conforming.")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(cleanup_p3_items())
