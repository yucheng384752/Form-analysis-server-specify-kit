"""
驗證 P3 遷移結果
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, func, text
from app.core.database import init_db, get_db_context
from app.models.p3_record import P3Record


async def main():
    await init_db()
    
    async with get_db_context() as db:
        # 統計 p3_records
        result = await db.execute(select(func.count()).select_from(P3Record))
        count = result.scalar()
        
        print(f"p3_records 總數: {count} 筆")
        print()
        
        # 列出所有記錄
        records_result = await db.execute(
            select(P3Record).order_by(P3Record.created_at)
        )
        
        print("詳細資料：")
        for r in records_result.scalars():
            print(f"  - lot_no: {r.lot_no_raw}")
            print(f"    date: {r.production_date_yyyymmdd}")
            print(f"    machine: {r.machine_no}")
            print(f"    mold: {r.mold_no}")
            print(f"    product_id: {r.product_id}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
