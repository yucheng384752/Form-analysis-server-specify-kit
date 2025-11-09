"""
Alembic 環境配置

配置資料庫遷移環境，支援自動產生遷移腳本。
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 添加專案路徑到 Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 匯入應用程式配置和模型
from app.core.config import get_settings
from app.core.database import Base

# 匯入所有模型以確保 metadata 完整
from app.models import UploadJob, UploadError, Record

# Alembic 配置物件
config = context.config

# 設定日誌配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 設定 target_metadata 用於自動產生遷移
target_metadata = Base.metadata

# 從環境變數取得資料庫連線 URL
settings = get_settings()
# 將異步 URL 轉換為同步版本給 Alembic 使用
db_url = settings.database_url
if db_url.startswith("postgresql+asyncpg://"):
    # 轉換為 psycopg2 版本給 Alembic 使用
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
elif db_url.startswith("sqlite+aiosqlite://"):
    # 轉換為同步 SQLite 版本給 Alembic 使用
    db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://")

config.set_main_option("sqlalchemy.url", db_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """
    離線模式執行遷移
    
    此模式僅使用 URL 配置上下文，不需要建立 Engine。
    適用於產生 SQL 腳本而非直接執行資料庫操作。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # 比較資料型別變更
        compare_server_default=True,  # 比較預設值變更
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    線上模式執行遷移
    
    此模式建立 Engine 並與資料庫建立連線，
    直接在資料庫上執行遷移操作。
    """
    # 建立資料庫引擎
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # 比較資料型別變更
            compare_server_default=True,  # 比較預設值變更
            # 包含物件名稱規則，用於命名約束
            render_as_batch=True,  # 支援 SQLite 批次模式
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
