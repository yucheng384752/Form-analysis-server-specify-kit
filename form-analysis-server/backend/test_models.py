"""
直接測試 SQLAlchemy 模型
"""
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase

# 直接匯入模型基類
class Base(DeclarativeBase):
    """Base class for all database models."""
    pass

# 設置 SQLite
DATABASE_URL = "sqlite+aiosqlite:///./dev_models_test.db"

# 手動匯入模型
import sys
sys.path.append('.')

# 匯入模型類
from app.models.upload_job import UploadJob, JobStatus
from app.models.record import Record
from app.models.upload_error import UploadError

async def test_models():
    """測試所有模型"""
    print("🚀 開始測試 SQLAlchemy 模型\n")
    
    try:
        # 創建引擎
        engine = create_async_engine(DATABASE_URL, echo=True)
        
        # 創建 session factory
        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        print(" 創建資料庫表格...")
        
        # 創建所有表格
        async with engine.begin() as conn:
            # 使用本地定義的 Base，並手動設置 metadata
            # 需要確保模型類使用這個 Base
            Base.metadata.create_all(bind=await conn.get_sync_connection())
            await conn.commit()
        
        print(" 表格創建成功!\n")
        
        # 測試 CRUD 操作
        async with session_factory() as session:
            print("📝 測試創建記錄...")
            
            # 1. 創建 UploadJob
            job = UploadJob(
                filename="test_upload.xlsx",
                file_size=2048000,
                status=JobStatus.PENDING,
                created_at=datetime.utcnow()
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            
            print(f" 創建工作: {job.id} - {job.filename}")
            
            # 2. 創建 Record
            record = Record(
                upload_job_id=job.id,
                lot_no="L240108001",
                product_name="測試產品 A",
                specification="規格說明",
                quantity=150,
                unit="pcs",
                raw_data={"column_a": "value_a", "column_b": "value_b"}
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            
            print(f" 創建記錄: {record.id} - {record.lot_no}")
            
            # 3. 創建 UploadError
            error = UploadError(
                upload_job_id=job.id,
                error_message="測試錯誤訊息",
                error_details={"row": 5, "column": "B", "issue": "格式錯誤"},
                created_at=datetime.utcnow()
            )
            session.add(error)
            await session.commit()
            await session.refresh(error)
            
            print(f" 創建錯誤: {error.id}")
            
            # 4. 測試關聯查詢
            print(f"\n 測試關聯查詢...")
            
            # 查詢工作及其記錄
            result = await session.execute(
                select(UploadJob).where(UploadJob.id == job.id)
            )
            job_with_data = result.scalar_one()
            
            # 載入關聯
            await session.refresh(job_with_data, ['records', 'errors'])
            
            print(f"   工作 {job_with_data.id}:")
            print(f"     - 記錄數量: {len(job_with_data.records)}")
            print(f"     - 錯誤數量: {len(job_with_data.errors)}")
            
            # 5. 測試更新
            print(f"\n📝 測試更新操作...")
            job_with_data.status = JobStatus.COMPLETED
            job_with_data.processed_at = datetime.utcnow()
            await session.commit()
            
            print(f" 更新工作狀態為: {job_with_data.status}")
            
            # 6. 測試查詢所有記錄
            print(f"\n 測試查詢統計...")
            
            all_jobs = await session.execute(select(UploadJob))
            job_count = len(all_jobs.scalars().all())
            
            all_records = await session.execute(select(Record))
            record_count = len(all_records.scalars().all())
            
            all_errors = await session.execute(select(UploadError))
            error_count = len(all_errors.scalars().all())
            
            print(f"   總工作數: {job_count}")
            print(f"   總記錄數: {record_count}")
            print(f"   總錯誤數: {error_count}")
        
        await engine.dispose()
        
        print(f"\n🎉 所有模型測試通過!")
        print(f"   資料庫檔案: {Path('dev_models_test.db').absolute()}")
        
        return True
        
    except Exception as e:
        print(f" 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_models())