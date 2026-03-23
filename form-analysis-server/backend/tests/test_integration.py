"""
整合測試 - 測試三個模型之間的完整交互
"""
import pytest
import uuid
from datetime import datetime, date
from sqlalchemy import select, func

from app.models.upload_job import UploadJob, JobStatus
from app.models.record import Record, DataType
from app.models.upload_error import UploadError
from tests.conftest import TestDataFactory


class TestModelsIntegration:
    """模型整合測試類"""
    
    @pytest.mark.asyncio
    async def test_complete_upload_workflow(self, db_session, clean_db):
        """測試完整的上傳工作流程"""
        
        # 1. 創建上傳工作
        job_data = TestDataFactory.upload_job_data(
            filename="integration_test.csv"
        )
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        assert job.status == JobStatus.PENDING
        print(f" 步驟1: 創建上傳工作 {job.id}")
        
        # 2. 開始驗證
        job.status = JobStatus.VALIDATED
        await db_session.commit()
        print(f" 步驟2: 驗證完成，狀態更新為 {job.status}")
        
        # 3. 創建成功記錄（這些記錄不與 UploadJob 直接關聯）
        success_records = []
        for i in range(5):
            record_data = TestDataFactory.record_data(
                lot_no=f"123456{i+1}_01",
                product_name=f"成功產品 {i+1}",
                quantity=100 + i * 10,
                production_date=date(2024, 1, i+1)
            )
            success_records.append(Record(**record_data))
        
        db_session.add_all(success_records)
        await db_session.commit()
        print(f" 步驟3: 創建 {len(success_records)} 筆成功記錄")
        
        # 4. 創建錯誤記錄
        error_scenarios = [
            (7, "lot_no", "INVALID_FORMAT", "批號格式錯誤"),
            (9, "quantity", "NEGATIVE_VALUE", "數量必須為正數")
        ]
        
        errors = []
        for row_index, field, error_code, message in error_scenarios:
            error_data = TestDataFactory.upload_error_data(
                job_id=job.id,
                row_index=row_index,
                field=field,
                error_code=error_code,
                message=message
            )
            errors.append(UploadError(**error_data))
        
        db_session.add_all(errors)
        await db_session.commit()
        print(f" 步驟4: 創建 {len(errors)} 筆錯誤記錄")
        
        # 5. 完成處理並更新統計
        job.status = JobStatus.IMPORTED
        job.total_rows = len(success_records) + len(errors)
        job.valid_rows = len(success_records)
        job.invalid_rows = len(errors)
        await db_session.commit()
        print(f" 步驟5: 處理完成，統計信息已更新")
        
        # 6. 驗證完整性
        
        # 驗證工作狀態
        final_job_result = await db_session.execute(
            select(UploadJob).where(UploadJob.id == job.id)
        )
        final_job = final_job_result.scalar_one()
        
        assert final_job.status == JobStatus.IMPORTED
        assert final_job.total_rows == 7
        assert final_job.valid_rows == 5
        assert final_job.invalid_rows == 2
        
        # 驗證成功記錄
        success_result = await db_session.execute(select(Record))
        success_records_from_db = success_result.scalars().all()
        assert len(success_records_from_db) == 5
        
        # 驗證錯誤記錄
        error_result = await db_session.execute(
            select(UploadError).where(UploadError.job_id == job.id)
        )
        errors_from_db = error_result.scalars().all()
        assert len(errors_from_db) == 2
        
        # 驗證外鍵關聯（只有 UploadError 與 UploadJob 有關聯）
        assert all(error.job_id == job.id for error in errors_from_db)
        
        print(f" 步驟6: 完整性驗證通過")
        print(f" 最終統計: 總計{final_job.total_rows}筆，有效{final_job.valid_rows}筆，無效{final_job.invalid_rows}筆")
    
    @pytest.mark.asyncio
    async def test_cascade_delete_integration(self, db_session, clean_db):
        """測試級聯刪除的完整流程"""
        
        # 創建工作
        job_data = TestDataFactory.upload_job_data(filename="cascade_test.csv")
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 創建記錄（獨立存在，不與 UploadJob 關聯）
        records = []
        for i in range(3):
            record_data = TestDataFactory.record_data(
                lot_no=f"CASCADE{i+1:02d}_01",
                product_name=f"級聯測試產品 {i+1}",
                quantity=100 + i * 10,
                production_date=date(2024, 1, i+1)
            )
            records.append(Record(**record_data))
        
        # 創建錯誤（與 UploadJob 關聯）
        errors = []
        for i in range(2):
            error_data = TestDataFactory.upload_error_data(
                job_id=job.id,
                row_index=i+1,
                field="test_field",
                error_code="TEST_ERROR",
                message=f"級聯測試錯誤 {i+1}"
            )
            errors.append(UploadError(**error_data))
        
        db_session.add_all(records + errors)
        await db_session.commit()
        
        # 驗證記錄存在
        record_count = await db_session.scalar(select(func.count(Record.id)))
        error_count = await db_session.scalar(
            select(func.count(UploadError.id)).where(UploadError.job_id == job.id)
        )
        
        assert record_count == 3
        assert error_count == 2
        print(f" 創建完成: {record_count} 筆記錄, {error_count} 筆錯誤")
        
        # 刪除工作（觸發級聯刪除）
        await db_session.delete(job)
        await db_session.commit()
        
        # 驗證 Record 不受影響（沒有外鍵關聯）
        remaining_records = await db_session.scalar(select(func.count(Record.id)))
        
        # 驗證 UploadError 被級聯刪除
        remaining_errors = await db_session.scalar(
            select(func.count(UploadError.id)).where(UploadError.job_id == job.id)
        )
        
        assert remaining_records == 3  # Record 不受影響
        assert remaining_errors == 0   # UploadError 被級聯刪除
        print(f" 級聯刪除成功: 錯誤已清除，記錄保持獨立")
    
    @pytest.mark.asyncio
    async def test_multiple_jobs_isolation(self, db_session, clean_db):
        """測試多個工作之間的資料隔離"""
        
        # 創建三個不同的工作
        jobs = []
        for i in range(3):
            job_data = TestDataFactory.upload_job_data(
                filename=f"isolation_test_{i+1}.csv"
            )
            job = UploadJob(**job_data)
            jobs.append(job)
        
        db_session.add_all(jobs)
        await db_session.commit()
        for job in jobs:
            await db_session.refresh(job)
        
        # 為每個工作創建不同數量的記錄和錯誤
        all_records = []
        all_errors = []
        
        for i, job in enumerate(jobs):
            # 工作1: 2筆記錄, 1筆錯誤
            # 工作2: 3筆記錄, 2筆錯誤
            # 工作3: 1筆記錄, 0筆錯誤
            record_count = i + 2 if i < 2 else 1
            error_count = i + 1 if i < 2 else 0
            
            # 創建記錄（獨立存在，不與特定工作關聯）
            for j in range(record_count):
                record_data = TestDataFactory.record_data(
                    lot_no=f"JOB{i+1}{j+1:02d}_01",
                    product_name=f"工作{i+1}_產品{j+1}",
                    quantity=100 + i * 10 + j,
                    production_date=date(2024, 1, (i+1) * 3 + j)
                )
                all_records.append(Record(**record_data))
            
            # 創建錯誤（與特定工作關聯）
            for j in range(error_count):
                error_data = TestDataFactory.upload_error_data(
                    job_id=job.id,
                    row_index=j+1,
                    field="test_field",
                    error_code="ISOLATION_ERROR",
                    message=f"工作{i+1}_錯誤{j+1}"
                )
                all_errors.append(UploadError(**error_data))
        
        db_session.add_all(all_records + all_errors)
        await db_session.commit()
        
        # 驗證每個工作的資料隔離
        for i, job in enumerate(jobs):
            # 查詢該工作的錯誤
            job_errors_result = await db_session.execute(
                select(UploadError).where(UploadError.job_id == job.id)
            )
            job_errors = job_errors_result.scalars().all()
            
            # 驗證數量
            expected_error_count = i + 1 if i < 2 else 0
            
            assert len(job_errors) == expected_error_count
            
            # 驗證資料屬於正確的工作
            assert all(error.job_id == job.id for error in job_errors)
            
            # 驗證資料內容隔離
            for error in job_errors:
                assert f"工作{i+1}" in error.message
            
            print(f" 工作{i+1}: {len(job_errors)}筆錯誤 - 隔離驗證通過")
        
        # 驗證記錄總數（所有記錄都是獨立的）
        total_records_result = await db_session.execute(select(Record))
        total_records = total_records_result.scalars().all()
        expected_total_records = 2 + 3 + 1  # 各工作的記錄數總和
        assert len(total_records) == expected_total_records
        print(f" 總記錄數驗證: {len(total_records)}筆記錄（獨立存在）")
    
    @pytest.mark.asyncio
    async def test_data_consistency_constraints(self, db_session, clean_db):
        """測試資料一致性約束"""
        
        # 創建工作
        job_data = TestDataFactory.upload_job_data()
        job = UploadJob(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # 測試記錄的批號唯一性（允許重複，因為沒有唯一約束）
        record1_data = TestDataFactory.record_data(
            lot_no="1234567_01",
            product_name="產品1",
            quantity=100,
            production_date=date(2024, 1, 1)
        )
        record1 = Record(**record1_data)
        db_session.add(record1)
        await db_session.commit()
        
        # 嘗試創建相同批號的記錄（應該被允許，因為沒有唯一約束）
        record2_data = TestDataFactory.record_data(
            lot_no="1234567_01",  # 相同批號
            data_type=DataType.P2,
            product_name="產品2",
            quantity=200,
            production_date=date(2024, 1, 2)
        )
        record2 = Record(**record2_data)
        db_session.add(record2)
        await db_session.commit()  # 這應該成功，因為沒有唯一約束
        
        # 驗證兩筆記錄都存在
        records_result = await db_session.execute(
            select(Record).where(Record.lot_no == "1234567_01")
        )
        records = records_result.scalars().all()
        assert len(records) == 2
        print(" 批號重複測試通過（允許重複）")
        
        # 測試資料型態一致性
        test_records = []
        test_cases = [
            {
                "lot_no": "9999999_99",
                "product_name": "測試產品A",
                "quantity": 0,  # 邊界值
                "production_date": date(1999, 12, 31)
            },
            {
                "lot_no": "0000001_01",
                "product_name": "測試產品B",
                "quantity": 999999,  # 大數值
                "production_date": date(2099, 12, 31)
            },
            {
                "lot_no": "1111111_11",
                "product_name": "測試產品C包含中文特殊字元!@#$%",
                "quantity": 12345,
                "production_date": date(2024, 2, 29)  # 閏年日期
            }
        ]
        
        for case in test_cases:
            record_data = TestDataFactory.record_data(**case)
            record = Record(**record_data)
            db_session.add(record)
            await db_session.commit()
            await db_session.refresh(record)
            test_records.append(record)
        
        # 驗證資料完整性
        for i, record in enumerate(test_records):
            case = test_cases[i]
            assert record.lot_no == case["lot_no"]
            assert record.product_name == case["product_name"]
            assert record.quantity == case["quantity"]
            assert record.production_date == case["production_date"]
        
        print(" 資料型態一致性測試通過")
        
        # 測試時間戳記一致性
        timestamps = []
        for i in range(3):
            record_data = TestDataFactory.record_data(
                lot_no=f"TIME{i:03d}_01",
                product_name=f"時間測試產品{i}",
                quantity=100 + i,
                production_date=date(2024, 1, i+1)
            )
            record = Record(**record_data)
            db_session.add(record)
            await db_session.commit()
            await db_session.refresh(record)
            timestamps.append(record.created_at)
        
        # 驗證時間戳記遞增（容忍毫秒級差異）
        for i in range(1, len(timestamps)):
            time_diff = (timestamps[i] - timestamps[i-1]).total_seconds()
            assert time_diff >= 0  # 後創建的記錄時間應該不早於前一個
            assert time_diff < 60   # 但差異不應超過1分鐘
        
        print(" 時間戳記一致性測試通過")
        
        # 測試 UploadError 與 UploadJob 的關聯一致性
        error_data = TestDataFactory.upload_error_data(
            job_id=job.id,
            row_index=100,
            field="consistency_test",
            error_code="CONSISTENCY_ERROR",
            message="一致性測試錯誤"
        )
        error = UploadError(**error_data)
        db_session.add(error)
        await db_session.commit()
        await db_session.refresh(error)
        
        assert error.job_id == job.id
        print(" 外鍵關聯一致性測試通過")
        
        print(f" 資料一致性測試完成：共測試 {len(test_records) + 3 + 2} 筆記錄")