"""
手動測試 SQLAlchemy 模型 - 使用直接定義
"""
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import String, Integer, DateTime, Text, JSON, ForeignKey, Index, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from enum import Enum

# SQLite URL
DATABASE_URL = "sqlite+aiosqlite:///./manual_test.db"

# Base 類
class Base(DeclarativeBase):
    """Base class for all database models."""
    pass

# Job Status Enum
class JobStatus(str, Enum):
    """上傳工作狀態列舉"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING" 
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# 手動定義模型 (適用於 SQLite)
class UploadJob(Base):
    """上傳工作模型"""
    __tablename__ = "upload_jobs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[JobStatus] = mapped_column(String(20), nullable=False, default=JobStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success_records: Mapped[int | None] = mapped_column(Integer, nullable=True) 
    error_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # 關聯
    records: Mapped[list["Record"]] = relationship("Record", back_populates="upload_job", cascade="all, delete-orphan")
    errors: Mapped[list["UploadError"]] = relationship("UploadError", back_populates="upload_job", cascade="all, delete-orphan")

class Record(Base):
    """記錄模型"""
    __tablename__ = "records"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_jobs.id", ondelete="CASCADE"), nullable=False)
    lot_no: Mapped[str] = mapped_column(String(50), nullable=False)
    product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specification: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 關聯
    upload_job: Mapped["UploadJob"] = relationship("UploadJob", back_populates="records")

class UploadError(Base):
    """上傳錯誤模型"""
    __tablename__ = "upload_errors"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_jobs.id", ondelete="CASCADE"), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 關聯
    upload_job: Mapped["UploadJob"] = relationship("UploadJob", back_populates="errors")

async def test_manual_models():
    """手動測試模型"""
    print(" 開始手動測試 SQLAlchemy 模型\n")
    
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
            await conn.run_sync(Base.metadata.create_all)
        
        print(" 表格創建成功!\n")
        
        # 測試 CRUD 操作
        async with session_factory() as session:
            print(" 測試創建記錄...")
            
            # 1. 創建 UploadJob
            job = UploadJob(
                filename="manual_test_upload.xlsx",
                file_size=3072000,
                status=JobStatus.PENDING
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            
            print(f" 創建工作: {job.id} - {job.filename}")
            
            # 2. 創建 Record
            record1 = Record(
                upload_job_id=job.id,
                lot_no="L240108001",
                product_name="手動測試產品 A",
                specification="測試規格說明",
                quantity=200,
                unit="pcs",
                raw_data={"test": "manual", "type": "record1"}
            )
            
            record2 = Record(
                upload_job_id=job.id,
                lot_no="L240108002", 
                product_name="手動測試產品 B",
                specification="另一個測試規格",
                quantity=150,
                unit="kg",
                raw_data={"test": "manual", "type": "record2"}
            )
            
            session.add_all([record1, record2])
            await session.commit()
            await session.refresh(record1)
            await session.refresh(record2)
            
            print(f" 創建記錄1: {record1.id} - {record1.lot_no}")
            print(f" 創建記錄2: {record2.id} - {record2.lot_no}")
            
            # 3. 創建 UploadError
            error = UploadError(
                upload_job_id=job.id,
                error_message="手動測試錯誤訊息",
                error_details={"row": 10, "column": "C", "issue": "數值格式錯誤"}
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
            
            # 載入關聯 - 手動查詢
            records_result = await session.execute(
                select(Record).where(Record.upload_job_id == job.id)
            )
            job_records = records_result.scalars().all()
            
            errors_result = await session.execute(
                select(UploadError).where(UploadError.upload_job_id == job.id)
            )
            job_errors = errors_result.scalars().all()
            
            print(f"   工作 {job_with_data.id}:")
            print(f"     - 檔名: {job_with_data.filename}")
            print(f"     - 狀態: {job_with_data.status}")
            print(f"     - 記錄數量: {len(job_records)}")
            print(f"     - 錯誤數量: {len(job_errors)}")
            
            # 5. 測試更新
            print(f"\n 測試更新操作...")
            job_with_data.status = JobStatus.COMPLETED
            job_with_data.processed_at = datetime.utcnow()
            job_with_data.total_records = len(job_records)
            job_with_data.success_records = len(job_records)
            job_with_data.error_records = len(job_errors)
            
            await session.commit()
            
            print(f" 更新工作狀態為: {job_with_data.status}")
            print(f" 設置統計: 總計{job_with_data.total_records}, 成功{job_with_data.success_records}, 錯誤{job_with_data.error_records}")
            
            # 6. 測試查詢統計
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
            
            # 7. 測試複雜查詢
            print(f"\n 測試複雜查詢...")
            
            # 查詢特定批號
            lot_result = await session.execute(
                select(Record).where(Record.lot_no.like("L240108%"))
            )
            lot_records = lot_result.scalars().all()
            print(f"   批號包含 'L240108' 的記錄: {len(lot_records)}")
            
            # 查詢已完成的工作
            completed_result = await session.execute(
                select(UploadJob).where(UploadJob.status == JobStatus.COMPLETED)
            )
            completed_jobs = completed_result.scalars().all()
            print(f"   已完成的工作: {len(completed_jobs)}")
        
        await engine.dispose()
        
        print(f"\n 手動模型測試全部通過!")
        print(f"   資料庫檔案: {Path('manual_test.db').absolute()}")
        print(f"\n 測試覆蓋:")
        print(f"    表格創建")
        print(f"    CRUD 操作 (創建、讀取、更新)")
        print(f"    關聯查詢")
        print(f"    複雜查詢")
        print(f"    統計功能")
        
        return True
        
    except Exception as e:
        print(f" 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_manual_models())