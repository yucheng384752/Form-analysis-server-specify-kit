"""
SQLite 開發環境設置和測試腳本
"""
import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import inspect
from app.core.database import engine, Base, get_db_context, init_db
from app.models import UploadJob, UploadError, Record
from app.models.upload_job import JobStatus
from app.schemas.upload_job_schema import UploadJobCreate
from app.schemas.record_schema import RecordCreate
import uuid
from datetime import datetime

async def setup_database():
    """初始化 SQLite 資料庫"""
    print(" 正在初始化 SQLite 資料庫...")
    
    # 初始化資料庫引擎
    await init_db()
    
    # 創建所有表格
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print(" 資料庫表格創建成功!")
    
    # 檢查表格
    async with engine.begin() as conn:
        inspector = await conn.run_sync(lambda sync_conn: inspect(sync_conn))
        tables = await conn.run_sync(lambda sync_conn: inspector.get_table_names())
        
        print(f" 創建的表格: {', '.join(tables)}")
        
        for table_name in tables:
            columns = await conn.run_sync(
                lambda sync_conn: inspector.get_columns(table_name)
            )
            print(f"   {table_name}: {len(columns)} 個欄位")

async def test_database_operations():
    """測試基本 CRUD 操作"""
    print("\n🧪 測試資料庫操作...")
    
    async with get_db_context() as session:
        # 創建測試工作
        test_job = UploadJob(
            filename="test_form.pdf",
            file_size=1024000,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        session.add(test_job)
        await session.commit()
        await session.refresh(test_job)
        
        print(f" 創建工作: {test_job.id} - {test_job.filename}")
        
        # 創建測試記錄
        test_record = Record(
            upload_job_id=test_job.id,
            lot_no="L240101001",
            product_name="測試產品",
            specification="測試規格",
            quantity=100,
            unit="pcs",
            raw_data={"test": "data"}
        )
        
        session.add(test_record)
        await session.commit()
        await session.refresh(test_record)
        
        print(f" 創建記錄: {test_record.id} - {test_record.lot_no}")
        
        # 測試關聯查詢
        from sqlalchemy import select
        
        result = await session.execute(
            select(UploadJob).where(UploadJob.id == test_job.id)
        )
        job_with_records = result.scalar_one()
        
        # 加載關聯記錄
        await session.refresh(job_with_records, ['records'])
        
        print(f" 工作關聯記錄數量: {len(job_with_records.records)}")
        
        # 創建錯誤記錄
        test_error = UploadError(
            upload_job_id=test_job.id,
            error_message="測試錯誤訊息",
            error_details={"line": 1, "column": "A"},
            created_at=datetime.utcnow()
        )
        
        session.add(test_error)
        await session.commit()
        
        print(f" 創建錯誤: {test_error.id}")
        
        return test_job, test_record, test_error

async def main():
    """主函數"""
    print(" SQLite 開發環境設置開始\n")
    
    # 檢查 .env.dev 文件
    env_file = Path(".env.dev")
    if not env_file.exists():
        print(" .env.dev 文件不存在!")
        return
    
    # 設置環境變數
    from dotenv import load_dotenv
    load_dotenv(".env.dev")
    
    print(f" 使用資料庫: {os.getenv('DATABASE_URL', '未設定')}")
    
    try:
        # 設置資料庫
        await setup_database()
        
        # 測試操作
        job, record, error = await test_database_operations()
        
        print(f"\n SQLite 開發環境設置完成!")
        print(f"   - 資料庫檔案: {Path('dev.db').absolute()}")
        print(f"   - 測試工作 ID: {job.id}")
        print(f"   - 測試記錄 ID: {record.id}")
        print(f"   - 測試錯誤 ID: {error.id}")
        
        print(f"\n 可以開始開發 API 端點了!")
        
    except Exception as e:
        print(f" 設置失敗: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())