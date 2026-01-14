"""
測試套件配置和共用工具
"""
import pytest
import asyncio
import os
import logging
from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# 設置測試環境變數
# NOTE: plain ':memory:' creates a separate DB per connection; use a named shared
# in-memory database URI so the schema is visible across connections.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared"
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "true"

from app.core.database import Base, init_db, close_db

# Import models early so they are registered on Base.metadata before create_all.
from app.models import UploadJob, Record, UploadError
from app.models.core.tenant import Tenant  # noqa: F401
from app.models.core.schema_registry import TableRegistry, SchemaVersion  # noqa: F401

# 測試資料庫引擎 (使用 shared-cache 記憶體 SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared"


def pytest_configure(config: pytest.Config) -> None:
    """Tune log verbosity for the test suite.

    Keep production logging behavior unchanged; only reduce common noisy loggers
    (SQLAlchemy engine echo, httpx request logs, request middleware).
    """
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("app.core.middleware").setLevel(logging.WARNING)
    logging.getLogger("app.services.import_v2").setLevel(logging.WARNING)

@pytest.fixture(scope="session")
def event_loop():
    """創建事件循環供整個測試會話使用"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    """創建測試資料庫引擎"""
    echo_sql = os.getenv("TEST_DATABASE_ECHO", "false").strip().lower() in {"1", "true", "yes", "y"}
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=echo_sql,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
            "uri": True,
        },
    )
    
    # 創建所有表格
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # 清理
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """創建資料庫會話，每個測試函數都會有獨立的會話"""
    
    # 創建會話工廠
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture(scope="function")
async def db_session_clean(clean_db, test_engine) -> AsyncGenerator[AsyncSession, None]:
    """A db session that is guaranteed to run on a clean schema.

    Use this for tests that must be runnable in isolation and should not
    be affected by data left behind in the shared in-memory SQLite DB.
    """
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()

@pytest.fixture(scope="function")
async def clean_db(test_engine):
    """在每個測試前後清理資料庫"""
    # 測試前清理
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield

    # 測試後不 drop schema：避免影響未使用 clean_db 的後續測試。

# 匯入模型枚舉和日期類型
from app.models.upload_job import JobStatus
import uuid
from datetime import date
from app.models.record import DataType

# 測試資料工廠
class TestDataFactory:
    """測試資料工廠類"""
    
    @staticmethod
    def upload_job_data(filename: str = "test_file.csv", **kwargs):
        """創建 UploadJob 測試資料"""
        default_data = {
            "filename": filename,
            "status": JobStatus.PENDING,
            "total_rows": 100,
            "valid_rows": 80,
            "invalid_rows": 20
        }
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def record_data(lot_no: str = "1234567_01", **kwargs):
        """創建 Record 測試資料"""
        default_data = {
            "lot_no": lot_no,
            "data_type": DataType.P1,
            "product_name": "測試產品",
            "quantity": 100,
            "production_date": date(2024, 1, 15)
        }
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def upload_error_data(job_id: uuid.UUID, **kwargs):
        """創建 UploadError 測試資料"""
        default_data = {
            "job_id": job_id,
            "row_index": 1,
            "field": "test_field",
            "error_code": "INVALID_FORMAT",
            "message": "測試驗證錯誤訊息"
        }
        default_data.update(kwargs)
        return default_data