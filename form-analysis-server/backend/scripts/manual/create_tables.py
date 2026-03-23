"""簡單的資料庫表格創建腳本"""

import asyncio
import sqlite3
from pathlib import Path

def create_tables():
    """使用SQLite創建資料庫表格"""
    db_path = Path("dev_database.db")
    
    # 創建連接
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f" 正在創建SQLite資料庫表格: {db_path}")
    
    # 創建records表格
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY,
        lot_no TEXT NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        production_date TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 創建索引
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS ix_records_lot_no ON records (lot_no)
    """)
    
    # 創建upload_jobs表格
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS upload_jobs (
        id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'PENDING',
        total_rows INTEGER,
        valid_rows INTEGER,
        invalid_rows INTEGER,
        process_id TEXT NOT NULL UNIQUE
    )
    """)
    
    # 創建upload_errors表格
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS upload_errors (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        row_index INTEGER NOT NULL,
        field TEXT NOT NULL,
        error_code TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES upload_jobs (id) ON DELETE CASCADE
    )
    """)
    
    # 插入一些測試資料
    test_data = [
        ('550e8400-e29b-41d4-a716-446655440000', '2503033_01', 'Test Product A', 100, '2025-01-01'),
        ('550e8400-e29b-41d4-a716-446655440001', '2503033_02', 'Test Product B', 200, '2025-01-02'),
        ('550e8400-e29b-41d4-a716-446655440002', '2503063_01', 'Test Product C', 150, '2025-01-03'),
    ]
    
    cursor.executemany("""
    INSERT OR REPLACE INTO records (id, lot_no, product_name, quantity, production_date)
    VALUES (?, ?, ?, ?, ?)
    """, test_data)
    
    # 提交變更
    conn.commit()
    
    # 檢查資料
    cursor.execute("SELECT COUNT(*) FROM records")
    count = cursor.fetchone()[0]
    print(f" 資料庫設置完成，包含 {count} 筆測試記錄")
    
    # 關閉連接
    conn.close()

if __name__ == "__main__":
    create_tables()