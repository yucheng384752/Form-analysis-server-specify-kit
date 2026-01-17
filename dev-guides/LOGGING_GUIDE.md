#  日誌系統說明文檔

##  日誌功能概覽

Form Analysis Spec Kit 具有完整的結構化日誌系統，提供詳細的應用程式監控和除錯資訊。

##  日誌配置

### 基本設定
- **日誌框架**: `structlog` (結構化日誌)
- **格式**: JSON (生產環境) / Console (開發環境)
- **等級**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **編碼**: UTF-8

### 環境變數配置
```bash
# .env 檔案
LOG_LEVEL=INFO          # 日誌等級
LOG_FORMAT=json         # 日誌格式 (json/console)
```

##  日誌檔案

### 檔案位置
```
form-analysis-server/backend/logs/
├── app.log             # 應用程式日誌 (所有等級)
├── app.log.1           # 輪轉備份檔案
├── app.log.2
├── error.log           # 錯誤日誌 (ERROR 以上)
├── error.log.1
└── error.log.2
```

### 檔案輪轉設定
- **檔案大小限制**: 10MB
- **備份檔案數量**: 5 個
- **自動輪轉**: 達到大小限制時自動建立新檔案

##  日誌內容

### 1. 請求日誌 (自動記錄)
```json
{
  "timestamp": "2025-11-09T10:30:00.123456Z",
  "level": "info",
  "event": "Request started",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "POST",
  "path": "/api/upload",
  "query_params": "",
  "client_host": "192.168.1.100",
  "user_agent": "Mozilla/5.0..."
}
```

### 2. 回應日誌 (自動記錄)
```json
{
  "timestamp": "2025-11-09T10:30:01.456789Z",
  "level": "info", 
  "event": "Request completed",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status_code": 200,
  "process_time": 1.333
}
```

### 3. 業務邏輯日誌

#### 檔案上傳
```json
{
  "timestamp": "2025-11-09T10:30:00.789Z",
  "level": "info",
  "event": "檔案上傳開始",
  "filename": "P1_2503033_01.csv"
}

{
  "timestamp": "2025-11-09T10:30:01.234Z", 
  "level": "info",
  "event": "檔案上傳和驗證完成",
  "process_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "P1_2503033_01.csv",
  "total_rows": 100,
  "valid_rows": 95,
  "invalid_rows": 5,
  "processing_time": 0.445
}
```

#### 資料查詢
```json
{
  "timestamp": "2025-11-09T10:31:00.123Z",
  "level": "info",
  "event": "開始查詢資料記錄",
  "search_term": "2503033",
  "page": 1,
  "page_size": 10
}

{
  "timestamp": "2025-11-09T10:31:00.234Z",
  "level": "info", 
  "event": "查詢完成",
  "search_term": "2503033",
  "total_count": 3,
  "returned_count": 3,
  "page": 1
}
```

#### 資料匯入
```json
{
  "timestamp": "2025-11-09T10:32:00.123Z",
  "level": "info",
  "event": "開始資料匯入",
  "process_id": "550e8400-e29b-41d4-a716-446655440000"
}

{
  "timestamp": "2025-11-09T10:32:01.456Z",
  "level": "info",
  "event": "資料匯入完成", 
  "process_id": "550e8400-e29b-41d4-a716-446655440000",
  "imported_rows": 95,
  "processing_time": 1.333
}
```

### 4. 錯誤日誌
```json
{
  "timestamp": "2025-11-09T10:33:00.123Z",
  "level": "error",
  "event": "檔案驗證失敗",
  "process_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "invalid_file.csv",
  "error_message": "批號格式錯誤",
  "exception": "ValidationError: 批號必須符合格式 ^\\d{7}_\\d{2}$",
  "stack_info": "..."
}
```

##  日誌查看和分析

### 1. 實時監控
```bash
# 監控所有日誌
tail -f logs/app.log

# 監控錯誤日誌
tail -f logs/error.log

# 過濾特定事件
tail -f logs/app.log | grep "檔案上傳"
```

### 2. 日誌分析
```bash
# 統計上傳次數
grep "檔案上傳開始" logs/app.log | wc -l

# 查看錯誤統計
grep -c "level.*error" logs/app.log

# 分析處理時間
grep "process_time" logs/app.log | jq '.process_time'
```

### 3. JSON 日誌查詢 (使用 jq)
```bash
# 查看今日上傳檔案
cat logs/app.log | jq 'select(.event == "檔案上傳開始" and (.timestamp | startswith("2025-11-09")))'

# 查看處理時間超過 1 秒的請求
cat logs/app.log | jq 'select(.process_time and (.process_time | tonumber) > 1)'

# 統計不同檔案類型的上傳次數
cat logs/app.log | jq -r 'select(.filename) | .filename' | cut -d'_' -f1 | sort | uniq -c
```

##  監控建議

### 1. 關鍵指標
- **上傳成功率**: (成功上傳 / 總上傳) * 100%
- **平均處理時間**: 檔案處理的平均時間
- **錯誤率**: (錯誤請求 / 總請求) * 100%
- **資料庫連線狀態**: 資料庫健康檢查結果

### 2. 告警設定
- 錯誤率超過 5%
- 平均處理時間超過 10 秒
- 磁碟空間不足 (日誌檔案過大)
- 資料庫連線失敗

### 3. 日常維護
- 定期檢查日誌檔案大小
- 清理過舊的備份檔案
- 監控錯誤趨勢
- 定期分析效能瓶頸

##  開發者使用指南

### 在程式碼中使用日誌
```python
from app.core.logging import get_logger

logger = get_logger(__name__)

# 資訊日誌
logger.info("處理開始", user_id=123, action="upload")

# 警告日誌
logger.warning("檔案大小接近限制", file_size=9.8, limit=10)

# 錯誤日誌 (自動包含異常資訊)
try:
    # 一些操作
    pass
except Exception as e:
    logger.error("操作失敗", operation="file_process", exc_info=True)
```

### 最佳實踐
1. **結構化資料**: 使用鍵值對記錄重要資訊
2. **一致性**: 相同事件使用相同的事件名稱
3. **上下文**: 包含足夠的上下文資訊進行除錯
4. **敏感資料**: 避免記錄敏感資訊 (密碼、個人資料)
5. **適當等級**: 使用合適的日誌等級

## �️ 日誌管理工具

### 1. 批次檔日誌監控工具 (Windows)
```batch
# 啟動日誌監控工具
scripts\monitor-logs.bat
```

功能包括：
-  查看應用程式日誌 (最新50行)
-  查看錯誤日誌 (最新50行)
- 即時監控日誌
- � 統計資訊 (日誌級別統計、API使用統計)
-  搜尋日誌內容
-  清理舊日誌備份

### 2. Python 日誌分析工具
```bash
# 生成完整分析報告
python tools\log_analyzer.py

# 即時監控模式
python tools\log_analyzer.py --watch

# 只顯示錯誤
python tools\log_analyzer.py --watch --errors-only

# 分析特定時間範圍
python tools\log_analyzer.py --hours 12
```

### 3. PowerShell 進階日誌管理工具
```powershell
# 啟動交互式選單
.\scripts\LogManager.ps1

# 直接執行特定功能
.\scripts\LogManager.ps1 -Action stats          # 統計資訊
.\scripts\LogManager.ps1 -Action view -Lines 100  # 查看最新100行
.\scripts\LogManager.ps1 -Action search -SearchTerm "錯誤"  # 搜尋
.\scripts\LogManager.ps1 -Action export         # 匯出為JSON
.\scripts\LogManager.ps1 -Action watch          # 即時監控
.\scripts\LogManager.ps1 -Action cleanup        # 清理舊日誌
```

### 4. 系統診斷工具
```batch
# 執行完整系統診斷
scripts\diagnose-system.bat
```

功能包括：
-  系統環境檢查 (Python, Node.js, Docker)
-  專案結構驗證
-  連接埠狀態檢查
-  日誌系統狀態
- 💾 磁碟空間監控
- 🌍 網路連接測試
-  Docker 容器狀態 (如果可用)
-  執行中的相關程序

##  日誌輪轉和清理

### 自動輪轉配置
系統會自動進行日誌輪轉：
- 當檔案超過 10MB 時自動輪轉
- 保留最近 5 個備份檔案
- 備份檔案命名格式：`app.log.1`, `app.log.2` 等
- 可通過 `.env.logging` 配置檔案調整設定

### 手動清理工具
```batch
# Windows 批次工具清理
scripts\monitor-logs.bat

# PowerShell 工具清理
.\scripts\LogManager.ps1 -Action cleanup

# Python 工具清理  
python tools\log_analyzer.py --cleanup
```

### Linux/Unix 自動清理腳本
```bash
#!/bin/bash
# cleanup-logs.sh

# 刪除 30 天前的日誌檔案
find logs/ -name "*.log.*" -mtime +30 -delete

# 壓縮 7 天前的日誌檔案
find logs/ -name "*.log.*" -mtime +7 ! -name "*.gz" -exec gzip {} \;

echo "日誌清理完成: $(date)"
```

### Cron 設定
```bash
# 每日凌晨 2 點執行日誌清理
0 2 * * * /path/to/cleanup-logs.sh >> /var/log/cleanup.log 2>&1
```

---

**最後更新**: 2025年11月9日