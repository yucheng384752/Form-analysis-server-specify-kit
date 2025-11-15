#!/usr/bin/env python3
"""
P1/P2/P3測試資料創建腳本

直接使用SQLAlchemy創建測試數據，無需啟動完整服務器。
"""

import asyncio
import sys
from pathlib import Path
from datetime import date

# 添加專案根目錄到 Python 路徑
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 暫時使用SQLite進行測試
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_p123.db"

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import String, Integer, Date, DateTime, func, Index, Text, Enum as SQLEnum, Float, delete, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON
from app.core.config import get_settings
from app.core.database import Base
from app.models.record import DataType
import uuid
from datetime import datetime

# 為SQLite重新定義Record模型
class TestRecord(Base):
    __tablename__ = "records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lot_no: Mapped[str] = mapped_column(String(50), nullable=False)
    data_type: Mapped[str] = mapped_column(String(10), nullable=False)
    production_date: Mapped[str] = mapped_column(String, nullable=True)
    
    # P1/P3 專用欄位
    product_name: Mapped[str] = mapped_column(String(100), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # P3 專用欄位
    p3_no: Mapped[str] = mapped_column(String(50), nullable=True)
    
    # P2 專用欄位
    sheet_width: Mapped[float] = mapped_column(Float, nullable=True)
    thickness1: Mapped[float] = mapped_column(Float, nullable=True)
    thickness2: Mapped[float] = mapped_column(Float, nullable=True)
    thickness3: Mapped[float] = mapped_column(Float, nullable=True)
    thickness4: Mapped[float] = mapped_column(Float, nullable=True)
    thickness5: Mapped[float] = mapped_column(Float, nullable=True)
    thickness6: Mapped[float] = mapped_column(Float, nullable=True)
    thickness7: Mapped[float] = mapped_column(Float, nullable=True)
    appearance: Mapped[int] = mapped_column(Integer, nullable=True)
    rough_edge: Mapped[int] = mapped_column(Integer, nullable=True)
    slitting_result: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # 額外數據
    additional_data: Mapped[str] = mapped_column(JSON, nullable=True)
    
    # 時間戳記
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat())


async def create_test_data():
    """創建P1/P2/P3測試資料"""
    
    # 使用SQLite進行測試
    engine = create_async_engine("sqlite+aiosqlite:///./test_p123.db")
    
    # 創建表格
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 創建會話
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    
    test_records = [
        # 批號 2503033_01 - P1資料
        TestRecord(
            id=str(uuid.uuid4()),
            lot_no="2503033_01",
            data_type="P1",
            product_name="產品A",
            quantity=100,
            production_date="2024-03-15",
            notes="高品質產品"
        ),
        TestRecord(
            id=str(uuid.uuid4()),
            lot_no="2503033_01", 
            data_type="P1",
            product_name="產品B",
            quantity=150,
            production_date="2024-03-15",
            notes="標準產品"
        ),
        
        # 批號 2503033_01 - P2資料
        TestRecord(
            id=str(uuid.uuid4()),
            lot_no="2503033_01",
            data_type="P2",
            sheet_width=7.985,
            thickness1=319.0,
            thickness2=325.0,
            thickness3=320.0,
            thickness4=319.0,
            thickness5=319.0,
            thickness6=326.0,
            thickness7=324.0,
            appearance=0,
            rough_edge=1,
            slitting_result=1,
            production_date="2024-03-15"
        ),
        TestRecord(
            id=str(uuid.uuid4()),
            lot_no="2503033_01",
            data_type="P2",
            sheet_width=8.123,
            thickness1=315.0,
            thickness2=322.0,
            thickness3=318.0,
            thickness4=321.0,
            thickness5=320.0,
            thickness6=323.0,
            thickness7=319.0,
            appearance=1,
            rough_edge=0,
            slitting_result=1,
            production_date="2024-03-15"
        ),
        
        # 批號 2503033_01 - P3資料
        TestRecord(
            id=str(uuid.uuid4()),
            lot_no="2503033_01",
            data_type="P3",
            p3_no="2503033012345",
            product_name="產品A",
            quantity=100,
            production_date="2024-03-15",
            notes="追蹤碼A"
        ),
        TestRecord(
            id=str(uuid.uuid4()),
            lot_no="2503033_01",
            data_type="P3",
            p3_no="2503033067890",
            product_name="產品B", 
            quantity=150,
            production_date="2024-03-15",
            notes="追蹤碼B"
        ),
        
        # 批號 2503044_01 - P1資料
        TestRecord(
            id=str(uuid.uuid4()),
            lot_no="2503044_01",
            data_type="P1",
            product_name="產品C",
            quantity=200,
            production_date="2024-03-20",
            notes="新產品測試"
        ),
        
        # 批號 2503044_01 - P2資料
        TestRecord(
            id=str(uuid.uuid4()),
            lot_no="2503044_01", 
            data_type="P2",
            sheet_width=7.750,
            thickness1=310.0,
            thickness2=315.0,
            thickness3=312.0,
            thickness4=314.0,
            thickness5=313.0,
            thickness6=316.0,
            thickness7=311.0,
            appearance=1,
            rough_edge=1,
            slitting_result=0,
            production_date="2024-03-20"
        ),
        
        # 批號 2503044_01 - P3資料
        TestRecord(
            id=str(uuid.uuid4()),
            lot_no="2503044_01",
            data_type="P3",
            p3_no="2503044098765",
            product_name="產品C",
            quantity=200,
            production_date="2024-03-20",
            notes="新追蹤碼"
        ),
        
        # 批號 2503055_01 - 只有P2資料
        TestRecord(
            id=str(uuid.uuid4()),
            lot_no="2503055_01",
            data_type="P2",
            sheet_width=8.000,
            thickness1=330.0,
            thickness2=335.0,
            thickness3=332.0,
            thickness4=334.0,
            thickness5=333.0,
            thickness6=336.0,
            thickness7=331.0,
            appearance=0,
            rough_edge=0,
            slitting_result=1,
            production_date="2024-03-25"
        )
    ]
    
    async with async_session() as session:
        try:
            # 清理現有資料
            await session.execute(delete(TestRecord))
            
            # 插入測試資料
            session.add_all(test_records)
            await session.commit()
            
            print(f" 成功創建 {len(test_records)} 筆測試資料")
            print("\n 測試資料摘要:")
            print("- 批號 2503033_01: P1(2筆) + P2(2筆) + P3(2筆)")
            print("- 批號 2503044_01: P1(1筆) + P2(1筆) + P3(1筆)")  
            print("- 批號 2503055_01: P2(1筆)")
            
            # 驗證資料
            
            # 統計各類型數量
            for data_type in ["P1", "P2", "P3"]:
                result = await session.execute(
                    select(func.count(TestRecord.id))
                    .where(TestRecord.data_type == data_type)
                )
                count = result.scalar()
                print(f"- {data_type} 類型: {count} 筆記錄")
            
            # 統計批號數量
            result = await session.execute(
                select(func.count(func.distinct(TestRecord.lot_no)))
            )
            lot_count = result.scalar()
            print(f"- 總批號數: {lot_count} 個")
            
        except Exception as e:
            await session.rollback()
            print(f" 創建測試資料失敗: {e}")
            raise
        finally:
            await engine.dispose()


async def main():
    """主函數"""
    print(" 開始創建 P1/P2/P3 測試資料")
    print("=" * 50)
    
    try:
        await create_test_data()
        print("=" * 50)
        print(" 測試資料創建完成！")
        print(" 資料庫檔案: ./test_p123.db")
        
    except Exception as e:
        print("=" * 50)
        print(f" 創建失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())