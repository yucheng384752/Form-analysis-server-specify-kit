import asyncio
import sys
import os
import json
from sqlalchemy import select

# Set DATABASE_URL explicitly
os.environ["DATABASE_URL"] = "postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db"

# Add current directory to sys.path
sys.path.append(os.getcwd())

from app.core import database
from app.models.record import Record, DataType
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item  # Import P2Item to resolve relationships

async def analyze_single_id():
    target_id = "20250902_P02_236-5_301"
    print(f"Analyzing Product ID: {target_id}")
    
    try:
        await database.init_db()
        
        async with database.async_session_factory() as session:
            # Fetch P3 Item with Record
            stmt = select(P3Item, Record).join(Record, P3Item.record_id == Record.id).where(P3Item.product_id == target_id)
            result = await session.execute(stmt)
            row = result.first()
            
            if not row:
                print("Product ID NOT FOUND in database.")
                return

            p3_item, record = row
            
            print("\n--- Data Sources Analysis ---")
            
            # 1. Date Analysis
            print(f"\n1. Date Component ('20250902'):")
            print(f"   - Source: Record.production_date")
            print(f"   - Value in DB: {record.production_date}")
            is_date_match = record.production_date.strftime('%Y%m%d') == "20250902"
            print(f"   - Match: {'YES' if is_date_match else 'NO'}")

            # 2. Machine Analysis
            print(f"\n2. Machine Component ('P02'):")
            print(f"   - Source 1: P3Item.row_data (Raw CSV Data)")
            row_data = p3_item.row_data or {}
            # Try common keys
            machine_keys = ['Machine NO', 'Machine No', 'Machine', 'machine_no', 'machine']
            found_machine_key = next((k for k in machine_keys if k in row_data), None)
            raw_machine = row_data.get(found_machine_key) if found_machine_key else "N/A"
            print(f"     - Key found: {found_machine_key}")
            print(f"     - Raw Value: {raw_machine}")
            
            print(f"   - Source 2: Record.machine_no (Fallback)")
            print(f"     - Value: {record.machine_no}")
            
            is_machine_match = str(raw_machine).strip() == "P02"
            print(f"   - Match (Raw Data): {'YES' if is_machine_match else 'NO'}")

            # 3. Mold Analysis
            print(f"\n3. Mold Component ('236-5'):")
            print(f"   - Source 1: P3Item.row_data (Raw CSV Data)")
            mold_keys = ['Mold NO', 'Mold No', 'Mold', 'mold_no', 'mold']
            found_mold_key = next((k for k in mold_keys if k in row_data), None)
            raw_mold = row_data.get(found_mold_key) if found_mold_key else "N/A"
            print(f"     - Key found: {found_mold_key}")
            print(f"     - Raw Value: {raw_mold}")
            
            print(f"   - Source 2: Record.mold_no (Fallback)")
            print(f"     - Value: {record.mold_no}")
            
            is_mold_match = str(raw_mold).strip() == "236-5"
            print(f"   - Match (Raw Data): {'YES' if is_mold_match else 'NO'}")

            # 4. Lot Analysis
            print(f"\n4. Lot Component ('301'):")
            print(f"   - Source 1: P3Item.row_data (Raw CSV Data)")
            lot_keys = ['lot', 'LOT', 'Lot']
            found_lot_key = next((k for k in lot_keys if k in row_data), None)
            raw_lot = row_data.get(found_lot_key) if found_lot_key else "N/A"
            print(f"     - Key found: {found_lot_key}")
            print(f"     - Raw Value: {raw_lot}")
            
            print(f"   - Source 2: Record.production_lot (Fallback)")
            print(f"     - Value: {record.production_lot}")
            
            is_lot_match = str(raw_lot).strip() == "301"
            print(f"   - Match (Raw Data): {'YES' if is_lot_match else 'NO'}")

            print("\n--- Conclusion ---")
            if is_date_match and is_machine_match and is_mold_match and is_lot_match:
                print("VERDICT: CORRECT. The Product ID is correctly derived from the raw row data.")
            else:
                print("VERDICT: INCORRECT or INCONSISTENT. Please check the mismatches above.")
                
            print("\n--- Raw Row Data Dump ---")
            print(json.dumps(row_data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(analyze_single_id())
