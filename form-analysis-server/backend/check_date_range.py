"""檢查資料日期範圍"""
import asyncio
from app.core.database import init_db, get_db_context
from sqlalchemy import select, func
from app.models.p3_item import P3Item
from app.models.p2_record import P2Record

async def main():
    await init_db()
    
    async with get_db_context() as db:
        # P3 日期範圍
        result = await db.execute(
            select(
                func.min(P3Item.production_date),
                func.max(P3Item.production_date),
                func.count(P3Item.id)
            )
        )
        row = result.one()
        print(f"P3 items: {row[2]} 筆")
        print(f"  日期範圍: {row[0]} to {row[1]}")
        
        # P2 created_at 範圍
        result2 = await db.execute(
            select(
                func.min(P2Record.created_at),
                func.max(P2Record.created_at),
                func.count(P2Record.id)
            )
        )
        row2 = result2.one()
        print(f"\nP2 records: {row2[2]} 筆")
        print(f"  日期範圍: {row2[0]} to {row2[1]}")

if __name__ == "__main__":
    asyncio.run(main())
