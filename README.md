# Form Analysis Spec Kit

表單分析規格套件 - 一個用於處理和分析表單資料的完整系統。

---

## 初學者指南 (推薦)

如果是第一次接觸本專案，或不熟悉前後端開發環境，請**務必使用此模式**。

### 1. 前置準備
請先下載並安裝 **Docker Desktop**：
- [下載 Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
- 安裝完成後，請啟動 Docker Desktop 並確保左下角顯示綠色的 "Engine running"。

### 2. 啟動系統
雙擊執行以下腳本：
```bash
.\scripts\start-system.bat
```
*(若出現 Windows 安全性警示，請點選「仍要執行」)*

### 3. 等待啟動
- 系統會自動下載所需元件並建立資料庫，首次啟動約需 **3-5 分鐘**。
- 當看到瀏覽器自動開啟並顯示登入畫面時，代表啟動成功！

### 4. 註冊 / 初始化（tenant + API key）

第一次啟動後，請到前端 `http://localhost:18003` 的「註冊 / 初始化（tenant + API key）」tab 完成初始化：

- 建立/選擇 tenant（空資料庫可按「自動初始化 Tenant」）
- （可選）貼上 raw API key 並保存（若後端啟用 `AUTH_MODE=api_key`）

完整流程與常見問題：getting-started/REGISTRATION_FLOW.md

---

## 開發者指南 (本地模式)

適合需要修改程式碼或進行除錯的開發人員。

### 1. 環境需求
- **Python 3.8+**: [下載 Python](https://www.python.org/downloads/)
- **Node.js 18+**: [下載 Node.js](https://nodejs.org/)
- **PostgreSQL 16+**: [下載 PostgreSQL](https://www.postgresql.org/download/)
  - 安裝時請記住密碼，並建立一個名為 `form_analysis` 的資料庫。
  - 預設端口需設為 `18001` (或修改 `.env` 設定)。

### 2. 首次安裝 (First Time Setup)
在執行啟動腳本前，請先開啟終端機 (Terminal) 執行以下指令安裝依賴：

**步驟 A: 設定後端**
```bash
cd form-analysis-server/backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

**步驟 B: 設定前端**
```bash
cd ../frontend
npm install
```

### 3. 啟動服務
完成上述安裝後，雙擊執行：
```bash
.\scripts\start_services.bat
```

---

## 常用指令與監控

### 系統操作
| 動作 | 指令 (Windows) | 說明 |
|------|---------------|------|
| **啟動系統** | `.\scripts\start-system.bat` | Docker 模式啟動 (推薦) |
| **停止系統** | `.\scripts\stop-system.bat` | 停止所有 Docker 服務 |
| **快速重啟** | `.\scripts\start_services.bat` | 本地開發模式啟動 |

### 監控與診斷
| 動作 | 指令 | 說明 |
|------|------|------|
| **後端日誌** | `.\scripts\monitor_backend.bat` | 查看 API 錯誤訊息 |
| **前端日誌** | `.\scripts\monitor_frontend.bat` | 查看網頁錯誤訊息 |
| **系統診斷** | `.\scripts\diagnose-system.bat` | 自動檢查環境問題 |

### 服務存取
- **前端應用**: http://localhost:18003/index.html
- **API 文檔**: http://localhost:18002/docs
- **資料庫**: localhost:18001 (PostgreSQL)

---

## 專案結構

```
Form-analysis-server-specify-kit/
├── README.md                    # 專案說明
├── form-analysis-server/        # 核心程式碼
│   ├── backend/                   # Python FastAPI 後端
│   ├── frontend/                  # React TypeScript 前端
│   └── docker-compose.yml         # Docker 設定檔
├── scripts/                     # 自動化腳本
├── docs/                        # 詳細文件
└── test-data/                   # 測試用 CSV 檔案
```

---

## 進階文件

- [產品需求文檔 (PRD)](docs/PRD2.md)
- [手動啟動指南](docs/MANUAL_STARTUP_GUIDE.md)
- [日誌管理工具](docs/LOG_MANAGEMENT_TOOLS.md)
- [DBeaver 資料庫連線指南](docs/DBEAVER_CONNECTION_GUIDE.md)

---

**最後更新**: 2025年12月25日
