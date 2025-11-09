"""
測試 UploadJob 模型
"""
import pytest
import uuid
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.upload_job import UploadJob, JobStatus
from app.models.upload_error import UploadError
from tests.conftest import TestDataFactory


class TestUploadJobModel:
    """UploadJob 模型測試類"""
    
    @pytest.mark.asyncio
    async def test_create_upload_job(self, db_session, clean_db):
        """測試創建基本的 UploadJob"""
        # 準備測試資料
        job_data = TestDataFactory.upload_job_data(
            filename="test_upload.csv"
        )
        
        # 創建工作
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 驗證
        assert job.id is not None
        assert isinstance(job.id, uuid.UUID)
        assert job.filename == "test_upload.csv"
        assert job.status == JobStatus.PENDING
        assert job.created_at is not None
        assert isinstance(job.created_at, datetime)
        assert job.total_rows == 100
        assert job.valid_rows == 80
        assert job.invalid_rows == 20
        assert job.process_id is not None
        assert isinstance(job.process_id, uuid.UUID)
    
    @pytest.mark.asyncio
    async def test_upload_job_with_errors_foreign_key(self, db_session, clean_db):
        """測試 UploadJob 與 UploadError 的外鍵關聯"""
        # 1. 創建 UploadJob
        job_data = TestDataFactory.upload_job_data(filename="error_test.csv")
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 2. 創建兩筆 UploadError
        error1_data = TestDataFactory.upload_error_data(
            job_id=job.id,
            row_index=1,
            field="product_name",
            error_code="REQUIRED_FIELD",
            message="產品名稱不能為空"
        )
        error1 = UploadError(**error1_data)
        
        error2_data = TestDataFactory.upload_error_data(
            job_id=job.id,
            row_index=2,
            field="quantity",
            error_code="INVALID_FORMAT", 
            message="數量格式錯誤"
        )
        error2 = UploadError(**error2_data)
        
        db_session.add_all([error1, error2])
        await db_session.commit()
        await db_session.refresh(error1)
        await db_session.refresh(error2)
        
        # 3. 驗證外鍵關聯
        assert error1.job_id == job.id
        assert error2.job_id == job.id
        assert error1.id != error2.id
        
        # 4. 測試關聯查詢
        result = await db_session.execute(
            select(UploadJob).where(UploadJob.id == job.id)
        )
        job_from_db = result.scalar_one()
        
        # 查詢關聯的錯誤
        error_result = await db_session.execute(
            select(UploadError).where(UploadError.job_id == job.id)
        )
        errors = error_result.scalars().all()
        
        assert len(errors) == 2
        assert all(error.job_id == job.id for error in errors)
        
        # 驗證錯誤內容
        error_messages = [error.message for error in errors]
        assert "產品名稱不能為空" in error_messages
        assert "數量格式錯誤" in error_messages
    
    @pytest.mark.asyncio
    async def test_upload_job_status_enum(self, db_session, clean_db):
        """測試 JobStatus 枚舉"""
        # 測試所有狀態值
        for status in JobStatus:
            job_data = TestDataFactory.upload_job_data(status=status)
            job = UploadJob(**job_data)
            db_session.add(job)
            await db_session.commit()
            await db_session.refresh(job)
            
            assert job.status == status
            
            # 清理以便下次測試
            await db_session.delete(job)
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_upload_job_update_status(self, db_session, clean_db):
        """測試更新 UploadJob 狀態"""
        # 創建工作
        job_data = TestDataFactory.upload_job_data()
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 記錄初始狀態
        assert job.status == JobStatus.PENDING
        
        # 更新狀態到 VALIDATED
        job.status = JobStatus.VALIDATED
        await db_session.commit()
        
        # 驗證更新
        result = await db_session.execute(
            select(UploadJob).where(UploadJob.id == job.id)
        )
        updated_job = result.scalar_one()
        assert updated_job.status == JobStatus.VALIDATED
        
        # 完成處理
        job.status = JobStatus.IMPORTED
        job.total_rows = 150
        job.valid_rows = 145
        job.invalid_rows = 5
        await db_session.commit()
        
        # 最終驗證
        result = await db_session.execute(
            select(UploadJob).where(UploadJob.id == job.id)
        )
        final_job = result.scalar_one()
        assert final_job.status == JobStatus.IMPORTED
        assert final_job.total_rows == 150
        assert final_job.valid_rows == 145
        assert final_job.invalid_rows == 5
    
    @pytest.mark.asyncio
    async def test_cascade_delete(self, db_session, clean_db):
        """測試級聯刪除功能"""
        # 創建工作
        job_data = TestDataFactory.upload_job_data()
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 創建錯誤記錄
        error_data = TestDataFactory.upload_error_data(job_id=job.id)
        error = UploadError(**error_data)
        db_session.add(error)
        await db_session.commit()
        
        # 驗證記錄存在
        error_count_before = await db_session.scalar(
            select(UploadError).where(UploadError.job_id == job.id)
        )
        assert error_count_before is not None
        
        # 刪除工作
        await db_session.delete(job)
        await db_session.commit()
        
        # 驗證錯誤記錄也被刪除 (級聯刪除)
        error_result = await db_session.execute(
            select(UploadError).where(UploadError.job_id == job.id)
        )
        errors_after = error_result.scalars().all()
        assert len(errors_after) == 0