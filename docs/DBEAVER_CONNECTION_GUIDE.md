# DBeaver 資料庫連線設定指南

## 概述
本指南說明如何使用 DBeaver 連線到 Form Analysis System 的 PostgreSQL 資料庫。

## 前置條件
- ✅ 系統已啟動（執行 `start-system.bat`）
- ✅ PostgreSQL 容器正在運行
- ✅ 已安裝 DBeaver Community 或 Enterprise 版本

## 資料庫連線資訊

### 預設配置（來自 docker-compose.yml）

```yaml
主機: localhost
端口: 5432
資料庫名稱: form_analysis_db
使用者名稱: app
密碼: app_secure_password
```

### 從環境變數讀取（可自訂）

資料庫配置可以透過 `.env` 檔案自訂：

**位置：** `form-analysis-server/backend/.env`

```ini
# 資料庫配置
POSTGRES_USER=app
POSTGRES_PASSWORD=app_secure_password
POSTGRES_DB=form_analysis_db
POSTGRES_PORT=5432
```

## DBeaver 連線步驟

### 1. 啟動系統並確認資料庫運行

```batch
# 在專案根目錄執行
cd scripts
start-system.bat
```

確認 PostgreSQL 容器狀態：
```bash
docker ps | findstr form_analysis_db
```

應該看到類似輸出：
```
form_analysis_db    postgres:16    Up 5 minutes (healthy)    0.0.0.0:5432->5432/tcp
```

### 2. 開啟 DBeaver 並創建新連線

1. 點擊 **Database** → **New Database Connection**
2. 選擇 **PostgreSQL**
3. 點擊 **Next**

### 3. 填入連線資訊

#### Main 標籤

| 欄位 | 值 | 說明 |
|------|-----|------|
| **Host** | `localhost` | 本地主機 |
| **Port** | `5432` | PostgreSQL 預設端口 |
| **Database** | `form_analysis_db` | 資料庫名稱 |
| **Username** | `app` | 使用者名稱 |
| **Password** | `app_secure_password` | 密碼 |
| **Show all databases** | ☑️ 勾選（可選） | 顯示所有資料庫 |
| **Save password** | ☑️ 勾選（建議） | 儲存密碼 |

#### PostgreSQL 標籤（進階設定）

| 設定 | 值 |
|------|-----|
| **Show databases** | `Show all databases` |
| **Show templates** | 取消勾選（可選） |

### 4. 測試連線

1. 點擊 **Test Connection** 按鈕
2. 第一次連線時，DBeaver 可能會提示下載 PostgreSQL JDBC 驅動
3. 點擊 **Download** 下載驅動
4. 如果連線成功，會顯示 ✅ "Connected"

### 5. 完成連線

點擊 **Finish** 或 **OK** 完成設定。

## 資料庫結構

連線成功後，您將看到以下表結構：

### 主要資料表

#### 1. `upload_jobs` - 上傳任務記錄
```sql
id              UUID PRIMARY KEY
filename        VARCHAR(255)
original_name   VARCHAR(255)
file_size       INTEGER
status          VARCHAR(50)
data_type       VARCHAR(10)  -- P1, P2, P3
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

#### 2. `records` - 資料記錄
```sql
id              UUID PRIMARY KEY
upload_job_id   UUID (FK → upload_jobs)
lot_no          VARCHAR(50)
product_name    VARCHAR(100)
quantity        INTEGER
data_type       VARCHAR(10)  -- P1, P2, P3
p1_specific     VARCHAR(255) -- P1 專屬欄位
p2_specific     VARCHAR(255) -- P2 專屬欄位
p3_specific     VARCHAR(255) -- P3 專屬欄位
created_at      TIMESTAMP
```

#### 3. `upload_errors` - 上傳錯誤記錄
```sql
id              UUID PRIMARY KEY
upload_job_id   UUID (FK → upload_jobs)
row_number      INTEGER
error_type      VARCHAR(100)
error_message   TEXT
raw_data        JSON
created_at      TIMESTAMP
```

### 常用查詢範例

```sql
-- 1. 查看所有上傳任務
SELECT id, filename, status, data_type, created_at 
FROM upload_jobs 
ORDER BY created_at DESC;

-- 2. 查看特定批號的資料
SELECT * FROM records 
WHERE lot_no = '2503063_02';

-- 3. 統計各資料類型的數量
SELECT data_type, COUNT(*) as count 
FROM records 
GROUP BY data_type;

-- 4. 查看上傳錯誤
SELECT uj.filename, ue.row_number, ue.error_message
FROM upload_errors ue
JOIN upload_jobs uj ON ue.upload_job_id = uj.id
ORDER BY ue.created_at DESC;

-- 5. 查看 P1 類型的資料（含專屬欄位）
SELECT lot_no, product_name, quantity, p1_specific
FROM records 
WHERE data_type = 'P1';
```

## 故障排除

### 問題 1: 無法連線

**錯誤訊息：** "Connection refused" 或 "Could not connect to server"

**解決方案：**
1. 確認 Docker 容器正在運行：
   ```bash
   docker ps | findstr postgres
   ```

2. 確認端口 5432 沒被佔用：
   ```bash
   netstat -an | findstr :5432
   ```

3. 重啟資料庫容器：
   ```bash
   cd form-analysis-server
   docker-compose restart db
   ```

### 問題 2: 密碼錯誤

**錯誤訊息：** "password authentication failed"

**解決方案：**
1. 檢查 `.env` 檔案中的密碼設定
2. 確認使用正確的密碼：預設為 `app_secure_password`
3. 如果修改過環境變數，需要重新創建容器：
   ```bash
   docker-compose down -v
   docker-compose up -d db
   ```

### 問題 3: 資料庫不存在

**錯誤訊息：** "database does not exist"

**解決方案：**
1. 檢查資料庫名稱是否正確：`form_analysis_db`
2. 重新初始化資料庫：
   ```bash
   docker-compose down -v
   .\scripts\start-system.bat
   ```

### 問題 4: 找不到表

**問題：** 連線成功但看不到任何表

**解決方案：**
1. 確認資料庫遷移已執行：
   ```bash
   docker logs form_analysis_api | findstr "migration"
   ```

2. 手動執行遷移：
   ```bash
   docker exec -it form_analysis_api alembic upgrade head
   ```

3. 檢查 Schema：確保在 DBeaver 中查看的是 `public` schema

## 進階設定

### 使用不同的連線參數

如果您修改了環境變數，請使用對應的值：

```bash
# 查看當前環境變數
docker exec form_analysis_db env | findstr POSTGRES
```

### 連線到不同環境

#### 本地開發環境
```
Host: localhost
Port: 5432
Database: form_analysis_db
```

#### Docker 內部連線（從其他容器）
```
Host: db
Port: 5432
Database: form_analysis_db
```

### 設定連線池（可選）

在 DBeaver 連線設定中，進入 **Connection settings** → **Performance**：

- Maximum pool size: 10
- Minimum pool size: 2
- Connection timeout: 30000 ms
- Validation query: `SELECT 1`

## 安全建議

1. **不要在生產環境使用預設密碼**
2. **修改密碼後記得更新 `.env` 檔案**
3. **限制資料庫訪問權限**
4. **定期備份資料庫**

```bash
# 備份資料庫
docker exec form_analysis_db pg_dump -U app form_analysis_db > backup.sql

# 還原資料庫
docker exec -i form_analysis_db psql -U app form_analysis_db < backup.sql
```

## 參考資料

- [DBeaver 官方文件](https://dbeaver.io/docs/)
- [PostgreSQL 官方文件](https://www.postgresql.org/docs/)
- 專案資料庫設定：`form-analysis-server/docker-compose.yml`
- 資料庫遷移檔案：`form-analysis-server/backend/alembic/versions/`

## 快速參考卡

```
┌─────────────────────────────────────────┐
│     DBeaver 快速連線資訊                │
├─────────────────────────────────────────┤
│ 主機:       localhost                   │
│ 端口:       5432                        │
│ 資料庫:     form_analysis_db            │
│ 使用者:     app                         │
│ 密碼:       app_secure_password         │
├─────────────────────────────────────────┤
│ 主要資料表:                             │
│  • upload_jobs   (上傳任務)             │
│  • records       (資料記錄)             │
│  • upload_errors (錯誤記錄)             │
└─────────────────────────────────────────┘
```

---

**最後更新：** 2025-11-15
**適用版本：** Form Analysis System v1.0
