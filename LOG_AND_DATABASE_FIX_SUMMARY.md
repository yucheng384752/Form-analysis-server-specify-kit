# 日誌檔案寫入與DBeaver連線問題解決總結

## 問題概述

### 問題 1: 日誌檔案內容為空
**現象**: CMD顯示API操作記錄,但 `app.log` 和 `error.log` 檔案大小為 0

**原因分析**:
- structlog 使用 `WriteLoggerFactory()` 配置
- `WriteLoggerFactory` 創建獨立的檔案物件直接寫入 stdout/stderr
- 未整合 Python 的 logging 模組,導致檔案處理器未被使用

### 問題 2: DBeaver 資料庫連線設定
**需求**: 查看 PostgreSQL 資料庫中的資料寫入內容

---

## 解決方案

### 1. 日誌檔案修復

#### 修改內容
檔案: `form-analysis-server/backend/app/core/logging.py`

**變更 1**: 更換 logger_factory
```python
# 修改前
structlog.configure(
    processors=processors,
    logger_factory=structlog.WriteLoggerFactory(),  #  只寫入 stdout
    ...
)

# 修改後
structlog.configure(
    processors=processors,
    logger_factory=structlog.stdlib.LoggerFactory(),  #  整合 Python logging
    ...
)
```

**變更 2**: 強制重新配置 logging
```python
# 清除現有處理器,防止重複
root_logger = logging.getLogger()
root_logger.handlers.clear()

# 強制重新配置
logging.basicConfig(
    level=log_level,
    format="%(message)s",
    handlers=[file_handler, error_file_handler, console_handler],
    force=True,  #  強制覆蓋現有配置
)
```

#### 執行步驟
```powershell
# 1. 重新建置後端容器
cd form-analysis-server
docker-compose build backend

# 2. 重啟後端服務
docker-compose up -d backend

# 3. 驗證日誌寫入
docker exec form_analysis_api cat /app/logs/app.log
docker exec form_analysis_api ls -lh /app/logs/
```

#### 驗證結果
```bash
# 日誌檔案大小
-rw-r--r-- 1 app app 15K Nov 15 09:29 app.log  #  成功寫入
-rw-r--r-- 1 app app   0 Nov  9 15:07 error.log
```

**日誌範例**:
```json
{
  "request_id": "eadc67e9-7031-4130-85c4-36cfd1e1ae54",
  "method": "GET",
  "path": "/healthz",
  "status_code": 200,
  "process_time": 0.001712,
  "event": "Request completed",
  "level": "info",
  "timestamp": "2025-11-15T09:27:23.305019Z"
}
```

---

### 2. DBeaver 連線設定

#### 完整文件
已創建詳細指南: **`docs/DBEAVER_CONNECTION_GUIDE.md`**

#### 快速設定參數

| 參數 | 值 |
|------|-----|
| **主機** | localhost |
| **Port** | 5432 |
| **資料庫** | form_analysis_db |
| **使用者名稱** | app |
| **密碼** | app_secure_password_change_in_production |

#### 連線步驟
1. 開啟 DBeaver → 新增連線 → PostgreSQL
2. 填入上述連線參數
3. 測試連線 → 完成

#### 可查看的資料表
- `upload_jobs` - 上傳任務記錄
- `records` - 資料記錄 (P1/P2/P3)
- `upload_errors` - 上傳錯誤記錄
- `alembic_version` - 資料庫版本

#### 測試查詢範例
```sql
-- 查看上傳任務
SELECT * FROM upload_jobs ORDER BY created_at DESC LIMIT 10;

-- 查看 P1 類型資料
SELECT * FROM records WHERE data_type = 'P1';

-- 統計各類型資料數量
SELECT data_type, COUNT(*) 
FROM records 
GROUP BY data_type;
```

---

## Git 提交記錄

```bash
commit 60be21d
Author: yucheng384752
Date: 2025-11-15

修復日誌檔案寫入問題並新增DBeaver連線指南

- 修復 structlog 配置:使用 stdlib.LoggerFactory 整合 Python logging
- 新增 force=True 強制重新配置 logging
- 清除現有 handlers 防止重複
- 新增完整的 DBeaver 連線設定指南
- 包含連線參數、故障排除和SQL範例

Files changed:
  - form-analysis-server/backend/app/core/logging.py (4 insertions, 3 deletions)
  - docs/DBEAVER_CONNECTION_GUIDE.md (new file, 317 lines)
```

---

## 技術說明

### structlog 與 Python logging 整合

**WriteLoggerFactory vs stdlib.LoggerFactory**:

| 特性 | WriteLoggerFactory | stdlib.LoggerFactory |
|------|-------------------|---------------------|
| 輸出方式 | 直接寫入 file-like 物件 | 透過 Python logging |
| 檔案處理器 |  不支援 |  完全支援 |
| RotatingFileHandler |  無效 |  有效 |
| 日誌等級過濾 |  受限 |  完整支援 |
| 多處理器輸出 |  困難 |  自動同步 |

**最佳實踐**:
```python
# 生產環境推薦配置
structlog.configure(
    logger_factory=structlog.stdlib.LoggerFactory(),  # 使用 stdlib
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# 搭配 Python logging
logging.basicConfig(
    handlers=[RotatingFileHandler(...)],
    force=True,  # 確保配置生效
)
```

---

## 驗證清單

- [x] 日誌檔案成功寫入 (app.log: 15KB)
- [x] JSON 格式日誌正確記錄
- [x] RotatingFileHandler 配置生效
- [x] DBeaver 連線參數文件化
- [x] 資料庫連線指南創建
- [x] Git 提交完成並推送

---

## 後續建議

### 日誌管理
1. **監控日誌大小**: 當前設定為 10MB 自動輪轉
2. **定期清理**: 保留最近 5 個備份檔案
3. **查看日誌**:
   ```powershell
   # 即時監控
   docker exec form_analysis_api tail -f /app/logs/app.log
   
   # 查看錯誤日誌
   docker exec form_analysis_api tail -f /app/logs/error.log
   ```

### 資料庫管理
1. **定期備份**:
   ```bash
   docker exec form_analysis_db pg_dump -U app form_analysis_db > backup.sql
   ```

2. **監控資料量**:
   ```sql
   SELECT 
     schemaname,
     tablename,
     pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables
   WHERE schemaname = 'public'
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
   ```

3. **效能優化**: 定期執行 VACUUM ANALYZE

---

## 相關文件

- [DBeaver 連線完整指南](./docs/DBEAVER_CONNECTION_GUIDE.md)
- [日誌管理工具](./docs/LOG_MANAGEMENT_TOOLS.md)
- [系統啟動指南](./scripts/start-system.bat)
- [資料庫設定文件](./form-analysis-server/backend/DATABASE_SETUP.md)

---

**建立時間**: 2025-11-15  
**最後更新**: 2025-11-15  
**問題狀態**:  已解決
