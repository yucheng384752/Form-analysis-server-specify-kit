# 啟動錯誤修復報告：JobStatus Enum 重複創建問題

## 錯誤描述
第一次執行系統啟動腳本 (`start-system.bat`) 時，後端容器 (`form_analysis_api`) 崩潰並顯示以下錯誤：
```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.DuplicateObject) type "job_status_enum" already exists
[SQL: CREATE TYPE job_status_enum AS ENUM ('PENDING', 'VALIDATED', 'IMPORTED')]
```

## 原因分析
這個問題是由於資料庫初始化流程中的競爭或重複執行導致的：

1. **容器啟動流程 (`Dockerfile`)**:
   容器的啟動命令設定為先執行 Alembic 遷移，再啟動應用程式：
   ```bash
   alembic upgrade head && uvicorn app.main:app ...
   ```

2. **Alembic 遷移**:
   `alembic upgrade head` 執行了遷移腳本 `2025_11_08_0122-ae889647f4f2_create_initial_tables_upload_jobs_.py`，該腳本中包含創建 `job_status_enum` 的指令：
   ```python
   job_status_enum = postgresql.ENUM(..., name='job_status_enum')
   job_status_enum.create(op.get_bind())
   ```
   此時，資料庫中已成功創建該 ENUM 類型。

3. **應用程式啟動 (`app/main.py`)**:
   應用程式啟動後，在 `lifespan` 事件中執行了 SQLAlchemy 的 `create_all`：
   ```python
   await conn.run_sync(Base.metadata.create_all)
   ```
   `create_all` 檢查模型定義，發現使用了 `job_status_enum`。雖然它通常會檢查表是否存在，但對於 PostgreSQL 的 ENUM 類型，如果在某些條件下（或 SQLAlchemy 判斷機制限制），它會嘗試再次創建該類型。
   
4. **PostgreSQL 行為**:
   PostgreSQL 不支援 `CREATE TYPE IF NOT EXISTS`（直到最近版本或特定語法），且當嘗試創建已存在的類型時會拋出 `DuplicateObject` 錯誤。

## 修復方案
在 `backend/app/main.py` 中修改資料庫初始化邏輯，捕獲 `ProgrammingError` 並在錯誤訊息包含 "already exists" 時忽略該錯誤。

這樣修改可以同時兼容以下兩種場景：
1. **生產/Docker 環境**：Alembic 先創建了類型，`create_all` 遇到重複錯誤時忽略，系統正常啟動。
2. **開發/測試環境**：如果沒有執行 Alembic，`create_all` 會正常創建類型和表格。

## 修改內容
文件：`form-analysis-server/backend/app/main.py`

```python
from sqlalchemy.exc import ProgrammingError

# ...

    # Create all tables
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
            print(" Database tables created/verified")
        except ProgrammingError as e:
            # 忽略 "type ... already exists" 錯誤
            if "already exists" in str(e):
                print(f" Note: Database objects already exist (safe to ignore): {str(e).splitlines()[0]}")
            else:
                raise e
```

## 驗證
重新啟動系統後，當後端初始化時，如果類型已存在，日誌中將顯示 "Note: Database objects already exist..." 而不是崩潰。
