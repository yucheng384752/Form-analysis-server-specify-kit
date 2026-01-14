"""
簡單的 SQLite 測試
"""
import asyncio
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from dotenv import load_dotenv

# 加載環境變數
load_dotenv(".env.dev")

# 手動設置資料庫 URL
DATABASE_URL = "sqlite+aiosqlite:///./dev_test.db"

print(f" 使用資料庫: {DATABASE_URL}")

async def test_basic_sqlite():
    """測試基本的 SQLite 連接"""
    try:
        # 創建引擎
        engine = create_async_engine(DATABASE_URL, echo=True)
        
        # 創建 session factory
        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # 測試連接
        async with session_factory() as session:
            result = await session.execute(select(1))
            value = result.scalar()
            print(f" SQLite 連接成功! 測試查詢結果: {value}")
        
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f" 連接失敗: {e}")
        return False

async def main():
    print(" 開始 SQLite 基本測試\n")
    
    success = await test_basic_sqlite()
    
    if success:
        print(f"\n SQLite 基本測試成功!")
        print(f"   資料庫檔案: {Path('dev_test.db').absolute()}")
    else:
        print(f"\n SQLite 測試失敗")

if __name__ == "__main__":
    asyncio.run(main())