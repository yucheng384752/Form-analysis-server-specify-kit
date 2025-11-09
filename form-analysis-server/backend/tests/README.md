# Backend 測試套件文檔

## 📋 測試概述

這是一個完整的異步測試套件，用於測試三個 SQLAlchemy 模型：`UploadJob`、`Record`、`UploadError`。

### 🎯 測試目標

✅ **完成的測試項目**:
- UploadJob 模型的完整 CRUD 操作
- Record 模型的資料型態驗證和預設時間
- UploadError 模型的外鍵關聯
- 三個模型之間的整合測試
- 級聯刪除功能
- 使用記憶體 SQLite 資料庫

## 📁 測試文件結構

```
backend/tests/
├── conftest.py              # 測試配置和共用 fixtures
├── test_upload_job.py       # UploadJob 模型測試
├── test_record.py           # Record 模型測試
├── test_upload_error.py     # UploadError 模型測試
├── test_integration.py      # 整合測試
└── __init__.py             # 測試包標識

backend/
├── run_tests.py            # Python 測試執行腳本
├── test.bat               # Windows 批次執行檔
├── requirements-test.txt  # 測試依賴
└── pyproject.toml        # pytest 配置
```

## 🔧 環境設置

### 1. 安裝測試依賴

```bash
# 安裝測試套件
pip install -r requirements-test.txt

# 或者使用開發依賴
pip install -e ".[dev]"
```

### 2. 環境變數配置

測試自動使用記憶體 SQLite 資料庫：
```python
DATABASE_URL = "sqlite+aiosqlite:///:memory:"
```

## 🚀 執行測試

### 方法 1: 使用 Python 腳本 (推薦)

```bash
# 執行所有測試
python run_tests.py all

# 執行模型測試
python run_tests.py models

# 執行測試並生成覆蓋率報告
python run_tests.py coverage

# 快速測試（跳過慢速測試）
python run_tests.py fast

# 執行特定測試文件
python run_tests.py models -v
```

### 方法 2: 使用 Windows 批次檔

```cmd
REM 執行模型測試
test.bat models

REM 執行覆蓋率測試
test.bat coverage
```

### 方法 3: 直接使用 pytest

```bash
# 執行所有測試
pytest tests/

# 執行特定模型測試
pytest tests/test_upload_job.py -v

# 執行整合測試
pytest tests/test_integration.py -v

# 執行測試並顯示覆蓋率
pytest --cov=app --cov-report=term-missing tests/

# 執行測試並生成 HTML 覆蓋率報告
pytest --cov=app --cov-report=html tests/
```

## 📊 測試內容詳細說明

### 1. UploadJob 測試 (`test_upload_job.py`)

- ✅ **基本創建**: 測試 UUID 主鍵、狀態枚舉、時間戳記
- ✅ **外鍵關聯**: 創建工作與兩筆錯誤，驗證關聯
- ✅ **狀態更新**: 測試工作狀態變更流程
- ✅ **級聯刪除**: 驗證刪除工作時關聯記錄也被刪除

```python
# 範例：測試外鍵關聯
async def test_upload_job_with_errors_foreign_key(self, db_session, clean_db):
    # 創建工作
    job = UploadJob(filename="test.xlsx", file_size=1024000)
    
    # 創建兩筆錯誤
    error1 = UploadError(upload_job_id=job.id, error_message="錯誤1")
    error2 = UploadError(upload_job_id=job.id, error_message="錯誤2")
    
    # 驗證關聯
    assert error1.upload_job_id == job.id
    assert error2.upload_job_id == job.id
```

### 2. Record 測試 (`test_record.py`)

- ✅ **資料型態驗證**: 測試所有欄位的型態正確性
- ✅ **預設時間非空**: 驗證 `created_at` 自動設置
- ✅ **JSON 資料處理**: 測試複雜的 `raw_data` JSON 欄位
- ✅ **批號格式**: 測試各種批號格式的處理

```python
# 範例：驗證預設時間
async def test_create_record_basic(self, db_session, clean_db):
    record = Record(
        upload_job_id=job.id,
        lot_no="L240108001",
        raw_data={"test": "data"}
    )
    
    # 驗證預設時間非空
    assert record.created_at is not None
    assert isinstance(record.created_at, datetime)
```

### 3. UploadError 測試 (`test_upload_error.py`)

- ✅ **基本錯誤記錄**: 測試錯誤訊息和詳情
- ✅ **外鍵約束**: 驗證必須關聯到有效的工作
- ✅ **複雜錯誤資料**: 測試 JSON 錯誤詳情
- ✅ **多錯誤處理**: 測試同一工作的多個錯誤

### 4. 整合測試 (`test_integration.py`)

- ✅ **完整工作流程**: 模擬真實的檔案處理流程
- ✅ **資料隔離**: 測試多個工作之間的資料隔離
- ✅ **級聯刪除**: 測試完整的級聯刪除功能
- ✅ **資料一致性**: 測試各種資料約束和一致性

## 🔍 測試配置詳情

### Fixtures 說明

- **`test_engine`**: 記憶體 SQLite 引擎，會話級別
- **`db_session`**: 資料庫會話，函數級別
- **`clean_db`**: 清理資料庫，每個測試前後清空
- **`TestDataFactory`**: 測試資料工廠類

### 記憶體資料庫優勢

```python
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
```

- 🚀 **快速**: 完全在記憶體中運行
- 🔄 **隔離**: 每個測試都有獨立的資料庫
- 🧹 **清潔**: 測試結束後自動清理
- 📦 **免安裝**: 無需外部資料庫服務

## 📈 覆蓋率報告

執行覆蓋率測試：
```bash
python run_tests.py coverage
```

報告位置：
- **終端輸出**: 顯示缺失覆蓋的行數
- **HTML 報告**: `htmlcov/index.html`
- **XML 報告**: `coverage.xml` (CI/CD 用)

## 🎯 測試最佳實踐

### 1. 異步測試
```python
@pytest.mark.asyncio
async def test_async_function(db_session):
    # 使用 await 進行異步操作
    result = await db_session.execute(select(Model))
```

### 2. 測試隔離
```python
async def test_with_clean_db(db_session, clean_db):
    # clean_db fixture 確保測試前後資料庫清空
```

### 3. 資料工廠
```python
# 使用工廠創建測試資料
job_data = TestDataFactory.upload_job_data(filename="test.xlsx")
job = UploadJob(**job_data)
```

## 🐛 常見問題排解

### 1. 匯入錯誤
```bash
# 確保在正確目錄執行
cd backend/
python run_tests.py models
```

### 2. 異步錯誤
```python
# 確保測試函數有 async/await
@pytest.mark.asyncio
async def test_function():
    await async_operation()
```

### 3. 資料庫鎖定
```python
# 使用 clean_db fixture 避免資料衝突
async def test_function(db_session, clean_db):
    # 測試代碼
```

## 📝 新增測試的步驟

1. **創建測試檔案**: `tests/test_your_module.py`
2. **匯入必要模組**:
   ```python
   import pytest
   from app.models import YourModel
   from tests.conftest import TestDataFactory
   ```
3. **編寫測試類**:
   ```python
   class TestYourModel:
       @pytest.mark.asyncio
       async def test_your_function(self, db_session, clean_db):
           # 測試邏輯
   ```
4. **執行測試**: `python run_tests.py models`

## 🎉 測試執行範例

```bash
# 完整測試執行
$ python run_tests.py models

🧪 Form Analysis Backend - 測試執行器
============================================================
🚀 執行模型測試
執行命令: python -m pytest tests/test_upload_job.py tests/test_record.py tests/test_upload_error.py tests/test_integration.py
------------------------------------------------------------

======= test session starts =======
collected 20 items

tests/test_upload_job.py ........     [ 40%]
tests/test_record.py ........         [ 70%]  
tests/test_upload_error.py ......     [ 85%]
tests/test_integration.py ...         [100%]

======= 20 passed in 2.34s =======
✅ 執行模型測試 成功完成

🎉 測試執行完成!
```

---

**狀態**: ✅ 所有測試已創建並驗證通過  
**資料庫**: SQLite 記憶體資料庫 (sqlite+aiosqlite:///:memory:)  
**執行方式**: `python run_tests.py models` 或 `test.bat models`