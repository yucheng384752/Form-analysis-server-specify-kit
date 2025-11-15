# 📊 日誌管理工具包

Form Analysis System 提供了完整的日誌管理工具包，支援日誌監控、分析、搜尋和清理等功能。

## 🛠️ 工具概覽

### 1. 📱 Windows 批次檔工具
**檔案**: `scripts/monitor-logs.bat`  
**用途**: 基礎日誌監控和管理  
**特色**: 簡單易用，無需額外依賴  

```batch
# 啟動工具
scripts\monitor-logs.bat
```

**功能**:
- 查看最新日誌 (app.log / error.log)
- 即時監控日誌變化
- 基本統計資訊
- 日誌搜尋
- 清理舊日誌備份

---

### 2. 🐍 Python 分析工具
**檔案**: `tools/log_analyzer.py`  
**用途**: 進階日誌分析和報告生成  
**特色**: 詳細統計分析，支援命令列參數  

```bash
# 生成完整分析報告
python tools/log_analyzer.py

# 即時監控模式
python tools/log_analyzer.py --watch

# 特定時間範圍分析
python tools/log_analyzer.py --hours 12

# 只顯示錯誤
python tools/log_analyzer.py --watch --errors-only
```

**功能**:
- 📈 API 使用統計 (上傳/查詢/匯入)
- 🔍 錯誤模式分析
- ⚡ 效能統計 (平均/最大/最小處理時間)
- 📊 日誌級別分佈
- 🕐 時間範圍篩選
- 📱 即時監控模式

---

### 3. 💻 PowerShell 進階工具
**檔案**: `scripts/LogManager.ps1`  
**用途**: 最完整的日誌管理解決方案  
**特色**: 彩色輸出，交互式選單，JSON 匯出  

```powershell
# 交互式選單
.\scripts\LogManager.ps1

# 直接執行功能
.\scripts\LogManager.ps1 -Action stats
.\scripts\LogManager.ps1 -Action view -Lines 100
.\scripts\LogManager.ps1 -Action search -SearchTerm "錯誤"
.\scripts\LogManager.ps1 -Action export
.\scripts\LogManager.ps1 -Action watch
.\scripts\LogManager.ps1 -Action cleanup
```

**功能**:
- 🎨 彩色輸出和表情符號
- 📤 JSON 格式匯出
- 📊 詳細統計資訊 (檔案大小、日誌級別分佈)
- 🔍 高亮搜尋結果
- 📈 即時監控 (格式化顯示)
- 🧹 智能清理 (確認對話)
- ⚙️  自定義參數

---

### 4. 🔍 系統診斷工具
**檔案**: `scripts/diagnose-system.bat`  
**用途**: 系統環境和狀態檢查  
**特色**: 綜合診斷報告，問題排查  

```batch
# 執行系統診斷
scripts\diagnose-system.bat
```

**功能**:
- 🖥️  系統環境檢查 (Python, Node.js, Docker)
- 📁 專案結構驗證
- 🌐 連接埠狀態檢查
- 📝 日誌系統狀態
- 💾 磁碟空間監控
- 🌍 網路連接測試
- 🐳 Docker 容器狀態
- 🔄 運行程序檢查
- 📋 診斷報告生成

## 📋 使用場景

### 🚀 開發階段
```bash
# 即時監控開發日誌
python tools/log_analyzer.py --watch

# 或使用 PowerShell 彩色輸出
.\scripts\LogManager.ps1 -Action watch
```

### 🔧 問題排查
```batch
# 1. 系統診斷
scripts\diagnose-system.bat

# 2. 查看錯誤日誌
scripts\monitor-logs.bat
# 選擇 [2] 查看錯誤日誌

# 3. 搜尋特定錯誤
.\scripts\LogManager.ps1 -Action search -SearchTerm "ConnectionError"
```

### 📊 性能分析
```bash
# 生成 24 小時性能報告
python tools/log_analyzer.py --hours 24

# 查看 API 統計
.\scripts\LogManager.ps1 -Action stats
```

### 🧹 日誌維護
```powershell
# 檢查日誌大小和清理
.\scripts\LogManager.ps1 -Action cleanup

# 匯出歷史日誌
.\scripts\LogManager.ps1 -Action export
```

## ⚙️ 配置選項

### 環境變數配置 (.env.logging)
```ini
# 日誌級別
LOG_LEVEL=INFO

# 日誌格式 (json/console)
LOG_FORMAT=json

# 檔案輪轉設定
MAX_LOG_SIZE=10485760  # 10MB
BACKUP_COUNT=5

# 效能日誌開關
ENABLE_PERFORMANCE_LOGGING=true
ENABLE_REQUEST_ID=true
```

### PowerShell 參數
```powershell
# 自定義日誌目錄
.\scripts\LogManager.ps1 -LogDir "custom/path/logs"

# 調整顯示行數
.\scripts\LogManager.ps1 -Action view -Lines 200

# 指定搜尋時間範圍
.\scripts\LogManager.ps1 -Hours 6
```

## 📈 輸出範例

### Python 分析報告
```
📊 Form Analysis System - 日誌分析報告
==================================================
📅 報告時間: 2024-11-09 15:30:45
📂 日誌目錄: form-analysis-server/backend/logs

📄 日誌檔案資訊:
   📝 app.log: 2,345,678 bytes (2.23 MB)
   🚨 error.log: 12,345 bytes (0.01 MB)

🔄 API 使用統計 (過去24小時):
   📡 UPLOAD:
      總請求: 25
      成功: 23
      錯誤: 2
      成功率: 92.0%

⚡ 效能統計:
   🎯 QUERY:
      平均處理時間: 145.67 ms
      最大處理時間: 892.34 ms
      最小處理時間: 23.45 ms
      樣本數: 156
```

### PowerShell 彩色輸出
```
[15:30:45] 📘 INFO: 檔案上傳開始 - filename: P1_test.csv
[15:30:46] ✅ INFO: 檔案驗證完成 - valid_rows: 100
[15:30:47] ⚠️ WARNING: 發現重複記錄 - duplicate_count: 3
[15:30:48] 📘 INFO: 上傳完成 - processing_time: 2.34s
```

## 🎯 最佳實踐

### 1. 日常監控
- 使用 `python tools/log_analyzer.py` 生成每日報告
- 設定計劃任務定期運行診斷工具
- 監控錯誤趨勢和效能變化

### 2. 問題排查
- 先運行系統診斷確認環境狀態
- 使用搜尋功能定位特定錯誤
- 結合即時監控觀察問題復現

### 3. 效能優化
- 定期分析 API 處理時間
- 監控日誌檔案大小增長
- 及時清理過期日誌備份

### 4. 安全維護
- 定期匯出重要日誌進行備份
- 避免在日誌中記錄敏感資訊
- 使用適當的日誌級別控制輸出

---

**完整文檔**: 查看 `form-analysis-server/backend/LOGGING_GUIDE.md` 獲取詳細的日誌配置和使用指南。