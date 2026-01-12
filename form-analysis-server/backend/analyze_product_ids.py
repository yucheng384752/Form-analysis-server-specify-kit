import asyncio
import sys
import os
import json
from datetime import date
from sqlalchemy import select

# Set DATABASE_URL explicitly
os.environ["DATABASE_URL"] = "postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db"

# Add current directory to sys.path
sys.path.append(os.getcwd())

from app.core import database
from app.models.record import Record, DataType
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item

async def analyze_product_ids():
    print("Starting Strict Product ID Analysis...")
    
    try:
        await database.init_db()
        
        async with database.async_session_factory() as session:
            # Fetch all P3 Items with their parent Records
            stmt = select(P3Item, Record).join(Record, P3Item.record_id == Record.id).where(Record.data_type == DataType.P3)
            result = await session.execute(stmt)
            rows = result.all()
            
            print(f"Total P3 items to analyze: {len(rows)}")
            print("-" * 100)
            print(f"{'ID':<38} | {'Status':<10} | {'Actual Product ID':<30} | {'Expected Product ID':<30} | {'Details'}")
            print("-" * 100)
            
            valid_count = 0
            invalid_count = 0
            
            for p3_item, record in rows:
                issues = []
                
                # 1. Source Data Extraction
                # Date
                prod_date = record.production_date
                if not prod_date:
                    issues.append("Missing Production Date in Record")
                    date_str = "00000000"
                else:
                    date_str = prod_date.strftime('%Y%m%d')
                
                # Row Data
                row_data = p3_item.row_data or {}
                
                # Machine
                # Priority: row_data -> p3_item column -> record column
                raw_machine = (
                    row_data.get('Machine NO') or row_data.get('Machine No') or row_data.get('Machine') or 
                    row_data.get('machine_no') or row_data.get('machine')
                )
                machine = str(raw_machine).strip() if raw_machine else (p3_item.machine_no or record.machine_no)
                if not machine:
                    issues.append("Missing Machine No")
                    machine = "UNKNOWN"
                
                # Mold
                raw_mold = (
                    row_data.get('Mold NO') or row_data.get('Mold No') or row_data.get('Mold') or 
                    row_data.get('mold_no') or row_data.get('mold')
                )
                mold = str(raw_mold).strip() if raw_mold else (p3_item.mold_no or record.mold_no)
                if not mold:
                    issues.append("Missing Mold No")
                    mold = "UNKNOWN"
                
                # Lot
                raw_lot = row_data.get('lot') or row_data.get('LOT') or row_data.get('Lot')
                lot = str(raw_lot).strip() if raw_lot else record.production_lot
                if not lot:
                    issues.append("Missing Lot")
                    lot = "UNKNOWN"
                
                # 2. Construct Expected ID
                expected_id = f"{date_str}-{machine}-{mold}-{lot}"
                
                # 3. Analyze
                actual_id = p3_item.product_id
                
                status = "VALID"
                details = ""
                
                if issues:
                    status = "INVALID"
                    details = "; ".join(issues)
                elif actual_id != expected_id:
                    status = "MISMATCH"
                    details = f"Components: Date={date_str}, Machine={machine}, Mold={mold}, Lot={lot}"
                
                if status == "VALID":
                    valid_count += 1
                else:
                    invalid_count += 1
                    print(f"{str(p3_item.id):<38} | {status:<10} | {str(actual_id):<30} | {expected_id:<30} | {details}")

            print("-" * 100)
            print(f"Analysis Complete.")
            print(f"Valid Items: {valid_count}")
            print(f"Invalid/Mismatch Items: {invalid_count}")
            
            if invalid_count == 0:
                print("\nSUCCESS: All P3 Items have strictly valid Product IDs based on their source data.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(analyze_product_ids())
