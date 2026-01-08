# 資料庫遷移執行指南

## 📋 遷移檔案清單

```
migrations/
├── 001_create_p3_items.sql      # 主要遷移腳本（必須執行）
├── 002_backfill_p3_items.sql    # 資料回填腳本（可選）
└── rollback_p3_items.sql        # 回滾腳本（緊急使用）
```

---

## 🚀 執行方式

### 方式 1: 使用 PowerShell（推薦）

#### Step 1: 設定環境變數

```powershell
# 設定資料庫連接資訊
$env:PGHOST = "localhost"
$env:PGPORT = "18001"
$env:PGDATABASE = "form_analysis_db"
$env:PGUSER = "app"
$env:PGPASSWORD = "app_secure_password_2024"
```

#### Step 2: 執行主要遷移

```powershell
# 切換到專案根目錄
cd C:\Users\yucheng\Desktop\Form-analysis-server-specify-kit

# 執行遷移腳本
psql -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER -d $env:PGDATABASE -f migrations\001_create_p3_items.sql
```

#### Step 3: （可選）執行資料回填

**注意**：僅在資料庫中已有 P3 資料時執行

```powershell
# 先檢查是否有 P3 資料
psql -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER -d $env:PGDATABASE -c "SELECT COUNT(*) FROM records WHERE data_type = 'P3';"

# 如果有資料，執行回填
psql -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER -d $env:PGDATABASE -f migrations\002_backfill_p3_items.sql
```

---

### 方式 2: 使用 Docker（如果資料庫在容器中）

#### Step 1: 找到資料庫容器

```powershell
docker ps | Select-String postgres
```

#### Step 2: 複製 SQL 檔案到容器

```powershell
docker cp migrations\001_create_p3_items.sql <container_id>:/tmp/
```

#### Step 3: 在容器內執行

```powershell
docker exec -it <container_id> psql -U app -d form_analysis_db -f /tmp/001_create_p3_items.sql
```

---

### 方式 3: 使用 DBeaver 或其他 GUI 工具

1. 打開 DBeaver
2. 連接到資料庫
3. 開啟 SQL 編輯器
4. 複製 `001_create_p3_items.sql` 內容
5. 執行腳本（F5 或執行按鈕）
6. 檢查輸出訊息

---

##  驗證遷移成功

### 1. 檢查表是否存在

```sql
SELECT tablename 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename = 'p3_items';
```

**預期結果**: 返回 `p3_items`

### 2. 檢查欄位結構

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'p3_items'
ORDER BY ordinal_position;
```

**預期結果**: 15 個欄位

### 3. 檢查索引數量

```sql
SELECT COUNT(*) 
FROM pg_indexes 
WHERE tablename = 'p3_items';
```

**預期結果**: 至少 12 個索引

### 4. 檢查外鍵約束

```sql
SELECT 
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'p3_items'
AND constraint_type = 'FOREIGN KEY';
```

**預期結果**: `fk_p3_items_record_id`

### 5. 測試插入資料

```sql
-- 測試插入一筆資料（需要先有 record）
INSERT INTO p3_items (
    record_id,
    row_no,
    lot_no,
    row_data
) VALUES (
    (SELECT id FROM records WHERE data_type = 'P3' LIMIT 1),
    1,
    'TEST_LOT',
    '{"test": "data"}'::jsonb
);

-- 檢查插入結果
SELECT * FROM p3_items ORDER BY created_at DESC LIMIT 1;

-- 清理測試資料
DELETE FROM p3_items WHERE lot_no = 'TEST_LOT';
```

---

## 常見問題排查

### 問題 1: psql 命令找不到

**解決方案**:
```powershell
# 方法 1: 安裝 PostgreSQL 客戶端工具
# 下載: https://www.postgresql.org/download/windows/

# 方法 2: 使用 Docker
docker exec -it <postgres_container> psql -U app -d form_analysis_db
```

### 問題 2: 連接被拒絕

**檢查項目**:
1. 資料庫是否啟動？
   ```powershell
   # 檢查 Docker 容器
   docker ps | Select-String postgres
   
   # 或檢查本地服務
   Get-Service | Where-Object {$_.Name -like "*postgres*"}
   ```

2. 端口是否正確？（預設 18001）
   ```powershell
   netstat -an | Select-String "18001"
   ```

3. 防火牆是否阻擋？

### 問題 3: 權限不足

**檢查使用者權限**:
```sql
-- 檢查當前使用者
SELECT current_user;

-- 檢查使用者權限
SELECT * FROM information_schema.role_table_grants 
WHERE grantee = 'app';
```

**授予權限**（如需要）:
```sql
GRANT ALL PRIVILEGES ON DATABASE form_analysis_db TO app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app;
```

### 問題 4: 表已存在

**處理方式**:
1. 如果要重新創建：
   ```sql
   DROP TABLE IF EXISTS p3_items CASCADE;
   ```
   然後重新執行遷移

2. 如果要保留現有表：
   - 腳本會自動跳過（已有 IF EXISTS 檢查）

---

## 🔄 回滾遷移

如果需要回滾（刪除 p3_items 表）：

```powershell
# 警告：這會永久刪除所有資料
psql -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER -d $env:PGDATABASE -f migrations\rollback_p3_items.sql
```

---

## 📊 執行前檢查清單

在執行遷移前，確認以下事項：

- [ ] 資料庫已啟動並可連接
- [ ] 已備份現有資料（重要！）
- [ ] 確認連接資訊正確（主機、端口、使用者、密碼）
- [ ] 已停止應用服務（避免衝突）
- [ ] 已閱讀遷移腳本內容
- [ ] 在測試環境先執行（建議）

---

## 🎯 執行後檢查清單

遷移完成後，確認以下事項：

- [ ] 表結構正確（15 個欄位）
- [ ] 索引已創建（12 個）
- [ ] 外鍵約束存在
- [ ] 觸發器正常運作
- [ ] 測試插入/查詢成功
- [ ] 應用程式可正常連接
- [ ] 日誌無錯誤訊息

---

## 📞 需要協助？

如果遇到問題：

1. 檢查 PostgreSQL 日誌
   ```powershell
   # Docker 容器日誌
   docker logs <postgres_container>
   
   # 本地日誌位置（Windows）
   # C:\Program Files\PostgreSQL\<version>\data\log\
   ```

2. 查看應用程式日誌
   ```powershell
   # 檢查後端日誌
   cat form-analysis-server\backend\logs\app.log
   ```

3. 參考文件
   - [PostgreSQL 官方文件](https://www.postgresql.org/docs/)
   - [SQLAlchemy 文件](https://docs.sqlalchemy.org/)

---

## 🚀 下一步

遷移完成後：

1.  重啟應用服務
2.  測試 P3 檔案匯入功能
3.  檢查進階搜尋功能
4.  監控系統日誌
5.  更新部署文件

---

**文件版本**: 1.0  
**最後更新**: 2025-01-22  
**作者**: GitHub Copilot
