"""
測試高級搜尋 API

驗證新增的 /api/query/records/advanced 端點功能
"""

import asyncio
from datetime import date
from sqlalchemy import select
from app.core.database import async_session_maker
from app.models.record import Record, DataType


async def test_advanced_search():
    """測試高級搜尋功能"""
    
    async with async_session_maker() as session:
        print("\n" + "=" * 60)
        print("高級搜尋 API 測試")
        print("=" * 60)
        
        # 測試 1: 按日期範圍搜尋
        print("\n測試 1: 按日期範圍搜尋")
        print("-" * 40)
        
        date_from = date(2025, 1, 1)
        date_to = date(2025, 12, 31)
        
        query = select(Record).where(
            Record.production_date >= date_from,
            Record.production_date <= date_to
        )
        result = await session.execute(query)
        records = result.scalars().all()
        
        print(f"日期範圍: {date_from} ~ {date_to}")
        print(f"找到記錄: {len(records)} 筆")
        
        # 測試 2: 按機台號碼搜尋
        print("\n測試 2: 按機台號碼模糊搜尋")
        print("-" * 40)
        
        machine_no = "P24"
        query = select(Record).where(
            Record.machine_no.ilike(f"%{machine_no}%")
        )
        result = await session.execute(query)
        records = result.scalars().all()
        
        print(f"機台號碼: {machine_no}")
        print(f"找到記錄: {len(records)} 筆")
        for r in records[:5]:  # 顯示前5筆
            print(f"  - {r.product_id} (機台: {r.machine_no}, 模具: {r.mold_no})")
        
        # 測試 3: 按模具編號搜尋
        print("\n測試 3: 按模具編號模糊搜尋")
        print("-" * 40)
        
        mold_no = "238"
        query = select(Record).where(
            Record.mold_no.ilike(f"%{mold_no}%")
        )
        result = await session.execute(query)
        records = result.scalars().all()
        
        print(f"模具編號: {mold_no}")
        print(f"找到記錄: {len(records)} 筆")
        for r in records[:5]:
            print(f"  - {r.product_id} (機台: {r.machine_no}, 模具: {r.mold_no})")
        
        # 測試 4: 按產品名稱搜尋 (P3規格)
        print("\n測試 4: 按產品名稱模糊搜尋")
        print("-" * 40)
        
        query = select(Record).where(
            Record.product_name.isnot(None)
        )
        result = await session.execute(query)
        records = result.scalars().all()
        
        print(f"有產品名稱的記錄: {len(records)} 筆")
        for r in records[:5]:
            print(f"  - {r.lot_no}: {r.product_name}")
        
        # 測試 5: 組合搜尋
        print("\n測試 5: 組合條件搜尋")
        print("-" * 40)
        
        query = select(Record).where(
            Record.data_type == DataType.P3,
            Record.machine_no.ilike("%P%"),
            Record.production_date >= date(2025, 1, 1)
        )
        result = await session.execute(query)
        records = result.scalars().all()
        
        print(f"條件: P3 類型 + 機台包含 'P' + 2025年後")
        print(f"找到記錄: {len(records)} 筆")
        
        # 統計資訊
        print("\n" + "=" * 60)
        print("資料庫統計")
        print("=" * 60)
        
        # 統計各類型記錄數
        for data_type in [DataType.P1, DataType.P2, DataType.P3]:
            query = select(func.count()).where(Record.data_type == data_type)
            from sqlalchemy import func
            result = await session.execute(query)
            count = result.scalar()
            print(f"{data_type.value} 記錄數: {count}")
        
        # 統計有 product_id 的記錄
        query = select(func.count()).where(Record.product_id.isnot(None))
        result = await session.execute(query)
        count = result.scalar()
        print(f"有 Product_ID 的記錄: {count}")
        
        print("\n測試完成")


if __name__ == "__main__":
    asyncio.run(test_advanced_search())
