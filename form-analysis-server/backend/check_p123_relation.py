"""檢查 P3 資料用於組合查詢"""
import asyncio
from datetime import date
from app.core.database import init_db, get_db_context
from sqlalchemy import select
from app.models.p3_item import P3Item
from app.models.p2_item import P2Item
from app.models.p1_record import P1Record

async def main():
    await init_db()
    
    async with get_db_context() as db:
        # 查詢 2026年1月的 P3 items
        result = await db.execute(
            select(P3Item).where(
                P3Item.production_date >= date(2026, 1, 1),
                P3Item.production_date < date(2026, 2, 1)
            ).limit(5)
        )
        p3_items = result.scalars().all()
        
        print(f"\n找到 {len(p3_items)} 筆 P3 items (2026-01)")
        
        for p3 in p3_items:
            print(f"\nP3: lot_no={p3.lot_no}, source_winder={p3.source_winder}, date={p3.production_date}")
            
            # 嘗試找 P2
            if p3.lot_no:
                p2_result = await db.execute(
                    select(P2Item).where(P2Item.lot_no == p3.lot_no).limit(1)
                )
                p2 = p2_result.scalar_one_or_none()
                if p2:
                    print(f"  → P2 found: lot_no={p2.lot_no}")
                    
                    # 嘗試找 P1
                    if p2.lot_no:
                        p1_result = await db.execute(
                            select(P1Record).where(P1Record.lot_no_norm == p2.lot_no).limit(1)
                        )
                        p1 = p1_result.scalar_one_or_none()
                        if p1:
                            print(f"    → P1 found: lot_no_norm={p1.lot_no_norm}")
                        else:
                            print(f"    → P1 NOT found (lot_no_norm={p2.lot_no})")
                else:
                    print(f"  → P2 NOT found (lot_no={p3.lot_no})")

if __name__ == "__main__":
    asyncio.run(main())
