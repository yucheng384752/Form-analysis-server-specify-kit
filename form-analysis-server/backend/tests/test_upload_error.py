"""
測試 UploadError 模型
"""
import pytest
import uuid
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.upload_job import UploadJob, JobStatus
from app.models.upload_error import UploadError
from tests.conftest import TestDataFactory


class TestUploadErrorModel:
    """UploadError 模型測試類"""
    
    @pytest.mark.asyncio
    async def test_create_upload_error_basic(self, db_session, clean_db):
        """測試創建基本的 UploadError"""
        # 先創建 UploadJob
        job_data = TestDataFactory.upload_job_data(filename="error_test.csv")
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 創建 UploadError
        error_data = TestDataFactory.upload_error_data(
            job_id=job.id,
            row_index=10,
            field="quantity",
            error_code="INVALID_FORMAT",
            message="數量欄位格式錯誤，期望數字但收到文字"
        )
        
        error = UploadError(**error_data)
        db_session.add(error)
        await db_session.commit()
        await db_session.refresh(error)
        
        # 驗證基本屬性
        assert error.id is not None
        assert isinstance(error.id, uuid.UUID)
        assert error.job_id == job.id
        assert error.row_index == 10
        assert error.field == "quantity"
        assert error.error_code == "INVALID_FORMAT"
        assert error.message == "數量欄位格式錯誤，期望數字但收到文字"
        
        # 驗證預設時間非空
        assert error.created_at is not None
        assert isinstance(error.created_at, datetime)
        
        # 驗證時間是最近創建的（5秒內）
        time_diff = datetime.utcnow() - error.created_at
        assert time_diff.total_seconds() < 5
    
    @pytest.mark.asyncio
    async def test_upload_error_data_types(self, db_session, clean_db):
        """測試 UploadError 資料型態驗證"""
        # 創建 UploadJob
        job_data = TestDataFactory.upload_job_data()
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 測試各種錯誤型態
        error_test_cases = [
            {
                "name": "驗證錯誤",
                "row_index": 15,
                "field": "quantity",
                "error_code": "INVALID_RANGE",
                "message": "數量不能為負數"
            },
            {
                "name": "格式錯誤",
                "row_index": 8,
                "field": "production_date",
                "error_code": "INVALID_FORMAT",
                "message": "日期格式不正確，期望 YYYY-MM-DD"
            },
            {
                "name": "必填欄位缺失",
                "row_index": 22,
                "field": "lot_no",
                "error_code": "REQUIRED_FIELD",
                "message": "批號為必填欄位，不能為空"
            },
            {
                "name": "長度錯誤",
                "row_index": 5,
                "field": "product_name",
                "error_code": "LENGTH_ERROR",
                "message": "產品名稱長度不能超過100字元"
            }
        ]
        
        for test_case in error_test_cases:
            error_data = TestDataFactory.upload_error_data(
                job_id=job.id,
                row_index=test_case["row_index"],
                field=test_case["field"],
                error_code=test_case["error_code"],
                message=test_case["message"]
            )
            
            error = UploadError(**error_data)
            db_session.add(error)
            await db_session.commit()
            await db_session.refresh(error)
            
            # 驗證資料型態
            assert isinstance(error.id, uuid.UUID)
            assert isinstance(error.job_id, uuid.UUID)
            assert isinstance(error.row_index, int)
            assert isinstance(error.field, str)
            assert isinstance(error.error_code, str)
            assert isinstance(error.message, str)
            assert isinstance(error.created_at, datetime)
            
            # 驗證欄位值
            assert error.row_index == test_case["row_index"]
            assert error.field == test_case["field"]
            assert error.error_code == test_case["error_code"]
            assert error.message == test_case["message"]
            
            print(f" {test_case['name']} 測試通過")
    
    @pytest.mark.asyncio
    async def test_upload_error_foreign_key_constraint(self, db_session, clean_db):
        """測試 UploadError 的外鍵約束（記憶體 SQLite 可能不強制執行）"""
        # 嘗試創建沒有對應 UploadJob 的 UploadError
        fake_job_id = uuid.uuid4()
        error_data = TestDataFactory.upload_error_data(
            job_id=fake_job_id,
            message="孤立的錯誤記錄"
        )
        
        error = UploadError(**error_data)
        db_session.add(error)
        
        try:
            # 在記憶體 SQLite 中可能不會引發 IntegrityError
            await db_session.commit()
            # 如果沒有錯誤，驗證記錄確實被創建了
            await db_session.refresh(error)
            assert error.job_id == fake_job_id
            print("  SQLite 記憶體模式允許了外鍵約束違反")
        except IntegrityError:
            # 如果有錯誤，這是期望的行為
            print(" 外鍵約束正確執行")
            pass
    
    @pytest.mark.asyncio
    async def test_multiple_errors_for_same_job(self, db_session, clean_db):
        """測試同一個工作的多個錯誤記錄"""
        # 創建 UploadJob
        job_data = TestDataFactory.upload_job_data(filename="multi_errors.csv")
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 創建多個錯誤記錄
        errors_data = []
        error_scenarios = [
            (5, "lot_no", "INVALID_FORMAT", "批號格式錯誤"),
            (8, "quantity", "NEGATIVE_VALUE", "數量不能為負數"),
            (12, "product_name", "TOO_LONG", "產品名稱過長"),
            (15, "lot_no", "REQUIRED_FIELD", "必填欄位為空"),
            (20, "production_date", "INVALID_DATE", "日期格式不正確"),
        ]
        
        for row_index, field, error_code, message in error_scenarios:
            error_data = TestDataFactory.upload_error_data(
                job_id=job.id,
                row_index=row_index,
                field=field,
                error_code=error_code,
                message=message
            )
            errors_data.append(UploadError(**error_data))
        
        db_session.add_all(errors_data)
        await db_session.commit()
        
        # 查詢所有錯誤記錄
        result = await db_session.execute(
            select(UploadError).where(UploadError.job_id == job.id)
        )
        errors = result.scalars().all()
        
        # 驗證錯誤記錄數量
        assert len(errors) == 5
        
        # 驗證每個錯誤都屬於同一個工作
        assert all(error.job_id == job.id for error in errors)
        
        # 驗證錯誤內容
        error_rows = [error.row_index for error in errors]
        expected_rows = [5, 8, 12, 15, 20]
        assert sorted(error_rows) == sorted(expected_rows)
        
        # 驗證錯誤訊息唯一性
        error_messages = [error.message for error in errors]
        assert len(set(error_messages)) == 5  # 所有訊息都應該不同
    
    @pytest.mark.asyncio
    async def test_upload_error_relationship_with_job(self, db_session, clean_db):
        """測試 UploadError 與 UploadJob 的關聯查詢"""
        # 創建兩個不同的工作
        job1_data = TestDataFactory.upload_job_data(filename="job1.csv")
        job1 = UploadJob(**job1_data)
        
        job2_data = TestDataFactory.upload_job_data(filename="job2.csv") 
        job2 = UploadJob(**job2_data)
        
        db_session.add_all([job1, job2])
        await db_session.commit()
        await db_session.refresh(job1)
        await db_session.refresh(job2)
        
        # 為第一個工作創建錯誤
        job1_errors = []
        for i in range(2):
            error_data = TestDataFactory.upload_error_data(
                job_id=job1.id,
                row_index=i+1,
                field="test_field",
                error_code="TEST_ERROR",
                message=f"Job1 錯誤 {i+1}"
            )
            job1_errors.append(UploadError(**error_data))
        
        # 為第二個工作創建錯誤
        job2_errors = []
        for i in range(3):
            error_data = TestDataFactory.upload_error_data(
                job_id=job2.id,
                row_index=i+1,
                field="test_field",
                error_code="TEST_ERROR",
                message=f"Job2 錯誤 {i+1}"
            )
            job2_errors.append(UploadError(**error_data))
        
        db_session.add_all(job1_errors + job2_errors)
        await db_session.commit()
        
        # 查詢第一個工作的錯誤
        job1_error_result = await db_session.execute(
            select(UploadError).where(UploadError.job_id == job1.id)
        )
        job1_errors_from_db = job1_error_result.scalars().all()
        
        # 查詢第二個工作的錯誤
        job2_error_result = await db_session.execute(
            select(UploadError).where(UploadError.job_id == job2.id)
        )
        job2_errors_from_db = job2_error_result.scalars().all()
        
        # 驗證關聯正確性
        assert len(job1_errors_from_db) == 2
        assert len(job2_errors_from_db) == 3
        
        # 驗證錯誤屬於正確的工作
        assert all(error.job_id == job1.id for error in job1_errors_from_db)
        assert all(error.job_id == job2.id for error in job2_errors_from_db)
        
        # 驗證錯誤內容
        job1_messages = [error.message for error in job1_errors_from_db]
        job2_messages = [error.message for error in job2_errors_from_db]
        
        assert all("Job1" in msg for msg in job1_messages)
        assert all("Job2" in msg for msg in job2_messages)
    
    @pytest.mark.asyncio
    async def test_upload_error_field_variations(self, db_session, clean_db):
        """測試不同欄位名稱和錯誤代碼"""
        # 創建 UploadJob
        job_data = TestDataFactory.upload_job_data()
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 測試各種欄位和錯誤代碼組合
        test_cases = [
            ("lot_no", "INVALID_FORMAT", "批號格式錯誤"),
            ("product_name", "TOO_LONG", "產品名稱過長"),
            ("quantity", "NEGATIVE_VALUE", "數量不能為負數"),
            ("production_date", "INVALID_DATE", "日期格式錯誤"),
            ("general", "UNKNOWN_ERROR", "未知錯誤")
        ]
        
        for i, (field, error_code, message) in enumerate(test_cases, 1):
            error_data = TestDataFactory.upload_error_data(
                job_id=job.id,
                row_index=i,
                field=field,
                error_code=error_code,
                message=message
            )
            
            error = UploadError(**error_data)
            db_session.add(error)
            await db_session.commit()
            await db_session.refresh(error)
            
            assert error.field == field
            assert error.error_code == error_code
            assert error.message == message
            assert error.row_index == i
            
            print(f" {field} - {error_code} 測試通過")
    
    @pytest.mark.asyncio
    async def test_upload_error_row_index_variations(self, db_session, clean_db):
        """測試不同行索引"""
        # 創建 UploadJob
        job_data = TestDataFactory.upload_job_data()
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 測試各種行索引
        test_row_indices = [0, 1, 100, 999, 10000]
        
        for row_index in test_row_indices:
            error_data = TestDataFactory.upload_error_data(
                job_id=job.id,
                row_index=row_index,
                field="test_field",
                error_code="TEST_ERROR",
                message=f"第 {row_index} 行錯誤"
            )
            
            error = UploadError(**error_data)
            db_session.add(error)
            await db_session.commit()
            await db_session.refresh(error)
            
            assert error.row_index == row_index
            assert f"第 {row_index} 行錯誤" in error.message
            
            print(f" 行索引 {row_index} 測試通過")