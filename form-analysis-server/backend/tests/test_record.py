"""
測試 Record 模型
"""
import pytest
import uuid
from datetime import datetime, date, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.record import Record
from tests.conftest import TestDataFactory


class TestRecordModel:
    """Record 模型測試類"""
    
    @pytest.mark.asyncio
    async def test_create_record_basic(self, db_session, clean_db):
        """測試創建基本的 Record"""
        # 創建 Record
        record_data = TestDataFactory.record_data(
            lot_no="1234567_01",
            product_name="測試產品A",
            quantity=150,
            production_date=date(2024, 1, 15)
        )
        
        record = Record(**record_data)
        db_session.add(record)
        await db_session.commit()
        await db_session.refresh(record)
        
        # 驗證基本屬性
        assert record.id is not None
        assert isinstance(record.id, uuid.UUID)
        assert record.lot_no == "1234567_01"
        assert record.product_name == "測試產品A"
        assert record.quantity == 150
        assert record.production_date == date(2024, 1, 15)
        
        # 驗證預設時間非空
        assert record.created_at is not None
        assert isinstance(record.created_at, datetime)
        
        # 驗證時間是最近創建的（5秒內）
        now = (
            datetime.now(record.created_at.tzinfo)
            if record.created_at.tzinfo
            else datetime.now(timezone.utc).replace(tzinfo=None)
        )
        time_diff = now - record.created_at
        assert time_diff.total_seconds() < 5
    
    @pytest.mark.asyncio
    async def test_record_data_types(self, db_session, clean_db):
        """測試 Record 資料型態驗證"""
        
        # 測試各種資料型態
        test_cases = [
            {
                "name": "完整資料",
                "data": {
                    "lot_no": "2240108_02",
                    "product_name": "完整測試產品",
                    "quantity": 200,
                    "production_date": date(2024, 1, 8)
                }
            },
            {
                "name": "最小必要資料", 
                "data": {
                    "lot_no": "3240108_03",
                    "product_name": "最小測試產品",
                    "quantity": 1,
                    "production_date": date(2024, 1, 1)
                }
            },
            {
                "name": "大數量測試",
                "data": {
                    "lot_no": "4240108_04",
                    "product_name": "大量產品",
                    "quantity": 999999,
                    "production_date": date(2023, 12, 31)
                }
            }
        ]
        
        for test_case in test_cases:
            record_data = TestDataFactory.record_data(**test_case["data"])
            
            record = Record(**record_data)
            db_session.add(record)
            await db_session.commit()
            await db_session.refresh(record)
            
            # 驗證資料型態
            assert isinstance(record.id, uuid.UUID)
            assert isinstance(record.lot_no, str)
            assert isinstance(record.product_name, str)
            assert isinstance(record.quantity, int)
            assert isinstance(record.production_date, date)
            assert isinstance(record.created_at, datetime)
            
            print(f" {test_case['name']} 測試通過")
    
    @pytest.mark.asyncio
    async def test_record_lot_no_variations(self, db_session, clean_db):
        """測試不同批號格式"""
        
        # 測試各種批號格式
        lot_nos = [
            "1234567_01",  # 標準格式
            "9876543_99",  # 不同序號
            "1111111_11",  # 重複數字
            "0000001_01",  # 前導零
        ]
        
        for i, lot_no in enumerate(lot_nos, 1):
            record_data = TestDataFactory.record_data(
                lot_no=lot_no,
                product_name=f"產品{i}",
                quantity=100 + i,
                production_date=date(2024, 1, i)
            )
            
            record = Record(**record_data)
            db_session.add(record)
            await db_session.commit()
            await db_session.refresh(record)
            
            assert record.lot_no == lot_no
            print(f" 批號 {lot_no} 測試通過")
    
    @pytest.mark.asyncio
    async def test_record_production_date_validation(self, db_session, clean_db):
        """測試生產日期驗證"""
        
        # 測試各種日期
        test_dates = [
            date(2024, 1, 1),   # 年初
            date(2024, 12, 31), # 年末  
            date(2023, 2, 28),  # 平年2月
            date(2024, 2, 29),  # 閏年2月
            date(2000, 1, 1),   # 千禧年
            date(1999, 12, 31), # 千禧年前
        ]
        
        for i, test_date in enumerate(test_dates, 1):
            record_data = TestDataFactory.record_data(
                lot_no=f"DATE{i:03d}_01",
                product_name=f"日期測試產品{i}",
                quantity=100,
                production_date=test_date
            )
            
            record = Record(**record_data)
            db_session.add(record)
            await db_session.commit() 
            await db_session.refresh(record)
            
            assert record.production_date == test_date
            print(f" 日期 {test_date} 測試通過")
    
    @pytest.mark.asyncio
    async def test_record_quantity_validation(self, db_session, clean_db):
        """測試數量驗證"""
        
        # 測試各種數量值
        quantities = [0, 1, 100, 999999, 1000000]
        
        for i, quantity in enumerate(quantities, 1):
            record_data = TestDataFactory.record_data(
                lot_no=f"QTY{i:03d}_{quantity:02d}",
                product_name=f"數量測試產品{i}",
                quantity=quantity,
                production_date=date(2024, 1, i)
            )
            
            record = Record(**record_data)
            db_session.add(record)
            await db_session.commit()
            await db_session.refresh(record)
            
            assert record.quantity == quantity
            print(f" 數量 {quantity} 測試通過")
    
    @pytest.mark.asyncio
    async def test_multiple_records_creation(self, db_session, clean_db):
        """測試批量創建記錄"""
        
        # 創建多筆記錄
        records_data = []
        for i in range(5):
            record_data = TestDataFactory.record_data(
                lot_no=f"BATCH00{i+1}_01",
                product_name=f"批量測試產品{i+1}",
                quantity=(i+1) * 100,
                production_date=date(2024, 1, i+1)
            )
            records_data.append(Record(**record_data))
        
        db_session.add_all(records_data)
        await db_session.commit()
        
        # 查詢所有記錄
        result = await db_session.execute(select(Record))
        records = result.scalars().all()
        
        # 驗證批量創建
        assert len(records) == 5
        
        # 驗證記錄內容
        lot_numbers = [record.lot_no for record in records]
        expected_lot_numbers = [f"BATCH00{i+1}_01" for i in range(5)]
        assert sorted(lot_numbers) == sorted(expected_lot_numbers)
        
        print(" 批量記錄創建測試通過")