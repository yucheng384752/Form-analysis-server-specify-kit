# 資料庫設置與遷移指南

## 📋 **已完成的工作**

✅ **SQLAlchemy 2.x 模型** (3個表格)
- `upload_jobs` - 檔案上傳工作記錄
- `upload_errors` - 錯誤記錄與位置資訊  
- `records` - 成功驗證的業務資料

✅ **Pydantic v2 Schemas** (API 請求/回應格式)
- 完整的 Create/Read 模型
- 資料驗證規則 (批號格式驗證等)

✅ **Alembic 遷移腳本**
- 初始遷移檔案: `2025_11_08_0122-ae889647f4f2_create_initial_tables_upload_jobs_.py`
- 完整的 SQL 腳本: `database_schema.sql`

---

## 🚀 **執行步驟**

### **方法 1: 使用 Docker Compose (推薦)**

1. **啟動 Docker Desktop**
   - 開啟 Docker Desktop 應用程式
   - 等待 Docker 服務完全啟動

2. **啟動資料庫服務**
   ```bash
   # 進入專案目錄
   cd "C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server"
   
   # 啟動 PostgreSQL 資料庫
   docker-compose up -d db
   
   # 檢查服務狀態
   docker-compose ps
   ```

3. **等待資料庫準備就緒**
   ```bash
   # 檢查資料庫日誌
   docker-compose logs db
   
   # 等待看到 "database system is ready to accept connections" 訊息
   ```

4. **執行資料庫遷移**
   ```bash
   # 進入後端目錄
   cd "C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\backend"
   
   # 檢查當前遷移狀態
   C:/Users/Yucheng/Desktop/form-analysis-sepc-kit/.venv/Scripts/alembic.exe current
   
   # 執行遷移
   C:/Users/Yucheng/Desktop/form-analysis-sepc-kit/.venv/Scripts/alembic.exe upgrade head
   
   # 確認遷移完成
   C:/Users/Yucheng/Desktop/form-analysis-sepc-kit/.venv/Scripts/alembic.exe current
   ```

### **方法 2: 手動執行 SQL 腳本**

如果 Docker 有問題，可以：

1. **安裝 PostgreSQL**
   - 下載並安裝 PostgreSQL 16
   - 創建資料庫: `form_analysis_db`
   - 創建用戶: `app` (密碼: `app_secure_password_change_in_production`)

2. **執行 SQL 腳本**
   ```bash
   # 使用 psql 連接資料庫
   psql -h localhost -p 5432 -U app -d form_analysis_db
   
   # 執行 SQL 腳本
   \i C:/Users/Yucheng/Desktop/form-analysis-sepc-kit/form-analysis-server/backend/database_schema.sql
   
   # 檢查表格創建
   \dt
   ```

---

## 🔍 **驗證步驟**

### **1. 檢查表格結構**
```sql
-- 連接資料庫後執行
\d+ upload_jobs
\d+ upload_errors  
\d+ records
```

### **2. 檢查索引**
```sql
-- 檢查所有索引
\di

-- 應該看到:
-- ix_upload_jobs_process_id (UNIQUE)
-- ix_upload_errors_job_id_row_index 
-- ix_records_lot_no
```

### **3. 檢查枚舉類型**
```sql
-- 檢查枚舉類型
\dT+ job_status_enum

-- 應該顯示: PENDING | VALIDATED | IMPORTED
```

---

## 🐛 **常見問題解決**

### **問題 1: Docker 連接失敗**
```
error during connect: ... dockerDesktopLinuxEngine
```
**解決方案**: 啟動 Docker Desktop 應用程式

### **問題 2: 資料庫連接超時**
```
psycopg.errors.ConnectionTimeout: connection timeout expired
```
**解決方案**: 
1. 確認 Docker 容器正在運行: `docker-compose ps`
2. 檢查資料庫日誌: `docker-compose logs db`
3. 等待資料庫完全啟動

### **問題 3: 遷移失敗**
**解決方案**:
1. 檢查 `.env` 文件中的 `DATABASE_URL`
2. 確認資料庫用戶權限
3. 使用離線模式生成 SQL: `alembic upgrade head --sql`

---

## 📊 **資料庫結構概覽**

```
PostgreSQL Database: form_analysis_db
├── upload_jobs (上傳工作)
│   ├── id (UUID, PK)
│   ├── process_id (UUID, UNIQUE INDEX) 
│   ├── filename, status, created_at
│   └── total_rows, valid_rows, invalid_rows
│
├── upload_errors (錯誤記錄) 
│   ├── id (UUID, PK)
│   ├── job_id (FK → upload_jobs.id)
│   ├── row_index, field, error_code, message
│   └── INDEX(job_id, row_index)
│
└── records (業務資料)
    ├── id (UUID, PK)  
    ├── lot_no (INDEX), product_name
    ├── quantity, production_date
    └── created_at
```

---

## 🔄 **下一步**

資料庫遷移完成後，您可以：

1. **測試 API** - 使用現有的健康檢查端點
2. **創建 CRUD API** - 實現上傳、驗證、匯入功能
3. **整合前端** - 連接 React 上傳界面
4. **端到端測試** - 完整檔案處理流程

準備好開始了嗎？請先啟動 Docker Desktop，然後執行上述步驟！