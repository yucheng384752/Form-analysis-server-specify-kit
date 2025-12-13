# Form Analysis Spec Kit

表單分析規格套件 - 一個用於處理和分析表單資料的完整系統。

##  專案結構

```
form-analysis-spec-kit/
├── docs/                           #  專案文檔
│   ├── PRD.md                     # 產品需求文檔
│   ├── PRD2.md                    # 產品需求文檔 v2
│   ├── README.md                  # 原始說明文檔
│   ├── RESTRUCTURE_PLAN.md        # 重構計劃
│   └── MANUAL_STARTUP_GUIDE.md    # 手動啟動指南
│
├── dev-docs/                       #  開發與維護文件（按月份歸檔）
│   ├── 2025-11/                   # 2025年11月開發文件
│   ├── 2025-12/                   # 2025年12月開發文件
│   └── README.md                  # 開發文件索引
│
├── scripts/                        # 系統腳本
│   ├── diagnose-system.bat        # 系統診斷腳本
│   ├── monitor_backend.bat        # 後端監控腳本
│   ├── monitor_frontend.bat       # 前端監控腳本
│   ├── start-system.bat           # 系統啟動腳本
│   ├── start-system.ps1           # PowerShell 啟動腳本
│   ├── start_services.bat         # 服務啟動腳本
│   ├── start_services.ps1         # PowerShell 服務腳本
│   └── stop-system.bat            # 系統停止腳本
│
├── test-data/                      #  測試資料
│   ├── P1/                        # P1 類型測試檔案
│   │   ├── P1_12345_6_error.csv
│   │   ├── P1_2411012_04_test_valid.csv
│   │   ├── P1_2503033_01.csv
│   │   ├── P1_invalid_batch_format.csv
│   │   └── P1_no_batch_number.csv
│   ├── P2/                        # P2 類型測試檔案
│   │   ├── P2_1234567890_01_too_long.csv
│   │   ├── P2_2503033_02_test_valid.csv
│   │   ├── P2_abc1234_99_error.csv
│   │   └── P2_wrong_format_123.csv
│   ├── P3/                        # P3 類型測試檔案
│   │   ├── P3_test_data.csv
│   │   └── P3_test_validation_errors.csv
│   └── test_data.csv              # 通用測試資料
│
├── legacy-components/              #  舊版組件
│   ├── CSVEditor.tsx              # 舊版 CSV 編輯器
│   └── FileUpload.tsx             # 舊版檔案上傳組件
│
├── tools/                          #  開發工具
│   ├── comprehensive_verification_test.py  # 綜合驗證測試
│   ├── fix_imports.py             # 匯入修復工具
│   ├── quick_start.py             # 快速啟動工具
│   └── test_server.py             # 測試伺服器
│
├── form-analysis-server/           #  主要應用程式
│   ├── backend/                   # 後端 API 服務
│   ├── frontend/                  # 前端 React 應用
│   └── docker-compose.yml         # Docker 編排設定
│
├── uploads/                        # 上傳檔案儲存
├── .venv/                         # Python 虛擬環境
└── .env.example                   # 環境變數範例
```

##  快速開始

### 選擇啟動方式

系統提供兩種啟動方式，請根據您的需求選擇：

#### 方式一：Docker 完整部署（推薦用於生產環境）
```bash
# 使用 Docker Compose 啟動完整系統
.\scripts\start-system.bat

# 或使用 PowerShell
.\scripts\start-system.ps1
```

**特點**：
- 完整的容器化環境（PostgreSQL + Backend + Frontend）
- 自動健康檢查和錯誤診斷
- 自動資料庫初始化和遷移
- 監控終端自動開啟
- **需要 Docker Desktop**
- **啟動時間較長（2-3 分鐘）**

**適用場景**：
- 第一次部署系統
- 正式環境部署
- 團隊開發（保證環境一致性）
- 完整功能測試

#### 方式二：本地開發模式（推薦用於日常開發）
```bash
# 直接啟動本地服務
.\scripts\start_services.bat

# 或使用 PowerShell
.\scripts\start_services.ps1
```

**特點**：
- 快速啟動（10-20 秒）
- 支援熱重載（即時看到代碼修改）
- 輕量級（不需要 Docker）
- 需手動啟動 PostgreSQL
- 需手動配置虛擬環境

**適用場景**：
- 日常開發調試
- 前端/後端單獨開發
- 快速測試修改
- 資源受限的電腦

**前置要求**：
1. PostgreSQL 服務已運行（端口 18001）
2. Python 虛擬環境已設置（`backend\venv`）
3. Node.js 已安裝

---

### 存取應用程式
- **前端應用**: http://localhost:18003/index.html
- **API 文檔**: http://localhost:18002/docs
- **API 測試**: http://localhost:18002/redoc
- **資料庫**: localhost:18001 (PostgreSQL)

### 停止系統

**Docker 模式**：
```bash
.\scripts\stop-system.bat
```

**本地開發模式**：
- 直接關閉啟動的終端視窗即可

## 功能說明

### 檔案上傳與驗證
- 支援 CSV 和 Excel (.xlsx) 格式（不支援 .xls）
- 自動驗證 lot_no 格式
- 檔案大小限制 10MB

### 資料查詢
- 批號查詢（lot_no）
- 產品名稱查詢
- 全文搜索
- 自動完成建議

### 資料管理
- PostgreSQL 資料庫
- 自動化資料匯入
- 錯誤記錄追蹤

## 開發工具

### 測試資料
使用 `test-data/` 目錄中的檔案進行功能測試：
- `P1/` - P1 類型檔案測試（包含有效和無效檔案）
- `P2/` - P2 類型檔案測試（包含各種錯誤情況）
- `P3/` - P3 類型檔案測試

### 舊版組件
`legacy-components/` 目錄保存了原始的 React 組件，供參考使用。

### 診斷工具
```bash
# 系統診斷
.\scripts\diagnose-system.bat

# 監控後端
.\scripts\monitor_backend.bat

# 監控前端  
.\scripts\monitor_frontend.bat
```

###  日誌管理工具
本系統提供完整的日誌管理工具包：

```batch
# Windows 批次檔日誌監控
scripts\monitor-logs.bat

# Python 日誌分析工具
python tools\log_analyzer.py

# PowerShell 進階日誌管理
.\scripts\LogManager.ps1
```

**主要功能：**
-  即時日誌監控
-  API 使用統計和效能分析
-  日誌搜尋和錯誤分析
-  自動日誌清理和備份管理
-  JSON 格式日誌匯出
-  彩色輸出和格式化顯示

詳細說明請參考：[日誌管理工具文檔](docs/LOG_MANAGEMENT_TOOLS.md)

##  技術棧

- **前端**: React + TypeScript + Vite
- **後端**: FastAPI + Python
- **資料庫**: PostgreSQL
- **容器化**: Docker + Docker Compose
- **樣式**: Tailwind CSS + shadcn/ui

##  環境要求

- Docker & Docker Compose
- Node.js 18+
- Python 3.8+
- PowerShell 5.0+（Windows）

---

**最後更新**: 2025年11月9日
