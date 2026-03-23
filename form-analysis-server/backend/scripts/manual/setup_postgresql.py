"""PostgreSQL 資料庫設置腳本

此腳本用於初始化PostgreSQL資料庫和表格結構。
系統只支援PostgreSQL資料庫。
"""

import asyncio
import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings
from app.core.database import Base
# 導入所有模型以確保表格創建
from app.models.record import Record
from app.models.upload_job import UploadJob  
from app.models.upload_error import UploadError
import uuid
from datetime import date, datetime


async def check_postgresql_connection():
    """檢查PostgreSQL連接"""
    settings = get_settings()
    
    if not settings.database_url.startswith('postgresql'):
        raise ValueError(
            f" 系統只支援PostgreSQL資料庫！當前配置: {settings.database_url[:30]}..."
        )
    
    print(f" 使用PostgreSQL資料庫: {settings.database_url}")
    
    # 測試連接
    engine = create_async_engine(settings.database_url)
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f" PostgreSQL連接成功: {version[:50]}...")
    except Exception as e:
        print(f" PostgreSQL連接失敗: {e}")
        raise
    finally:
        await engine.dispose()


async def create_tables():
    """創建資料庫表格"""
    settings = get_settings()
    
    engine = create_async_engine(settings.database_url)
    
    try:
        print(" 正在創建資料庫表格...")
        
        # 創建所有表格
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print(" 資料庫表格創建完成")
        
        # 插入測試資料
        await insert_test_data(engine)
        
    except Exception as e:
        print(f" 表格創建失敗: {e}")
        raise
    finally:
        await engine.dispose()


async def insert_test_data(engine):
    """插入測試資料"""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from app.models.record import Record
    
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    
    test_records = [
        Record(
            id=uuid.uuid4(),
            lot_no="2503033_01",
            product_name="Test Product A",
            quantity=100,
            production_date=date(2025, 1, 1)
        ),
        Record(
            id=uuid.uuid4(),
            lot_no="2503033_02", 
            product_name="Test Product B",
            quantity=200,
            production_date=date(2025, 1, 2)
        ),
        Record(
            id=uuid.uuid4(),
            lot_no="2503063_01",
            product_name="Test Product C", 
            quantity=150,
            production_date=date(2025, 1, 3)
        ),
    ]
    
    async with async_session() as session:
        try:
            # 檢查是否已有資料
            from sqlalchemy import select, func
            result = await session.execute(select(func.count(Record.id)))
            existing_count = result.scalar()
            
            if existing_count > 0:
                print(f" 資料庫已包含 {existing_count} 筆記錄，跳過測試資料插入")
                return
            
            # 插入測試資料
            session.add_all(test_records)
            await session.commit()
            
            print(f" 成功插入 {len(test_records)} 筆測試記錄")
            
        except Exception as e:
            await session.rollback()
            print(f" 測試資料插入失敗: {e}")
            raise


async def main():
    """主函數"""
    print(" PostgreSQL 資料庫設置開始")
    print("=" * 50)
    
    try:
        # 1. 檢查PostgreSQL連接
        await check_postgresql_connection()
        
        # 2. 創建表格和測試資料
        await create_tables()
        
        print("=" * 50)
        print(" PostgreSQL 資料庫設置完成！")
        
    except Exception as e:
        print("=" * 50)
        print(f" 設置失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())