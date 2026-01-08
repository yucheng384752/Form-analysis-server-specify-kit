import asyncio
import sys
import os
import re
from datetime import date
from sqlalchemy import select

# Set DATABASE_URL explicitly
os.environ["DATABASE_URL"] = "postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db"

# Add current directory to sys.path
sys.path.append(os.getcwd())

from app.core import database
from app.models.record import Record, DataType
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item  # Import P2Item to resolve relationships

def parse_p3_date(date_str):
    if not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    # 1. Try Chinese ROC format: 114年09月02日
    chinese_match = re.match(r'(\d{2,3})年(\d{1,2})月(\d{1,2})日', date_str)
    if chinese_match:
        try:
            roc_year = int(chinese_match.group(1))
            month = int(chinese_match.group(2))
            day = int(chinese_match.group(3))
            return date(roc_year + 1911, month, day)
        except ValueError:
            pass

    # 2. Try Slash/Dash ROC format: 114/09/02 or 114-09-02
    roc_match = re.match(r'(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})', date_str)
    if roc_match:
        try:
            year_part = int(roc_match.group(1))
            # If year is 2 or 3 digits, assume ROC. If 4, assume AD.
            if year_part < 1000:
                year = year_part + 1911
            else:
                year = year_part
            
            month = int(roc_match.group(2))
            day = int(roc_match.group(3))
            return date(year, month, day)
        except ValueError:
            pass
            
    return None

async def migrate_logic():
    print("Starting P3 Product ID Logic Migration (Row Data Date Priority)...")
    
    try:
        await database.init_db()
        
        async with database.async_session_factory() as session:
            # Fetch all P3 Items with Record
            stmt = select(P3Item, Record).join(Record, P3Item.record_id == Record.id).where(Record.data_type == DataType.P3)
            result = await session.execute(stmt)
            rows = result.all()
            
            print(f"Found {len(rows)} P3 items to process.")
            
            updated_count = 0
            
            # Track seen IDs to handle duplicates within this batch
            seen_ids = set()
            
            # First pass: Collect existing IDs in DB that we are NOT updating?
            # Actually, simpler to just track what we generate in this run.
            # If we generate a collision with an existing ID that isn't being changed, we might fail.
            # But we are updating ALL P3 items. So we just need to ensure uniqueness among the new set.
            
            for p3_item, record in rows:
                row_data = p3_item.row_data or {}
                
                # 1. Extract Date
                # Priority: row_data -> record.production_date
                date_obj = None
                
                # Try to find date in row_data
                date_keys = ['year-month-day', 'Year-Month-Day', 'Date', '年月日', '日期']
                found_key = next((k for k in date_keys if k in row_data), None)
                
                if found_key:
                    raw_date = row_data[found_key]
                    date_obj = parse_p3_date(raw_date)
                    if date_obj:
                        # print(f"  [Item {p3_item.id}] Found date in row_data ({found_key}): {raw_date} -> {date_obj}")
                        pass
                
                if not date_obj:
                    # Fallback to record
                    date_obj = record.production_date
                
                if not date_obj:
                    print(f"Skipping Item {p3_item.id}: No date found in row_data or record.")
                    continue
                
                date_str = date_obj.strftime('%Y%m%d')
                
                # 2. Machine
                machine = None
                machine_keys = ['Machine NO', 'Machine No', 'Machine', 'machine_no', 'machine']
                found_machine = next((k for k in machine_keys if k in row_data), None)
                if found_machine:
                    machine = row_data[found_machine]
                
                if not machine:
                    machine = p3_item.machine_no or record.machine_no
                
                if not machine:
                    print(f"Skipping Item {p3_item.id}: No machine found.")
                    continue
                
                machine = str(machine).strip()

                # 3. Mold
                mold = None
                mold_keys = ['Mold NO', 'Mold No', 'Mold', 'mold_no', 'mold']
                found_mold = next((k for k in mold_keys if k in row_data), None)
                if found_mold:
                    mold = row_data[found_mold]
                
                if not mold:
                    mold = p3_item.mold_no or record.mold_no
                
                if not mold:
                    print(f"Skipping Item {p3_item.id}: No mold found.")
                    continue
                    
                mold = str(mold).strip()
                
                # 4. Lot
                lot = None
                lot_keys = ['lot', 'LOT', 'Lot']
                found_lot = next((k for k in lot_keys if k in row_data), None)
                if found_lot:
                    lot = row_data[found_lot]
                
                if not lot:
                    lot = record.production_lot
                
                if not lot:
                    print(f"Skipping Item {p3_item.id}: No lot found.")
                    continue
                
                lot = str(lot).strip()
                
                # Construct ID
                base_id = f"{date_str}_{machine}_{mold}_{lot}"
                new_id = base_id
                
                # Handle duplicates
                dup_count = 1
                while new_id in seen_ids:
                    new_id = f"{base_id}_{dup_count}"
                    dup_count += 1
                
                seen_ids.add(new_id)
                
                if p3_item.product_id != new_id:
                    print(f"Updating Item {p3_item.id}: {p3_item.product_id} -> {new_id}")
                    p3_item.product_id = new_id
                    updated_count += 1
            
            if updated_count > 0:
                print(f"Committing {updated_count} changes...")
                await session.commit()
                print("Migration completed.")
            else:
                print("No changes needed.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(migrate_logic())
