#  表單分析系統 (Form Analysis Spec Kit)

> 現代化的表單資料處理系統，支援 CSV 檔案上傳、驗證、預覽和匯入功能

[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-blue.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-blue.svg)](https://www.typescriptlang.org/)

## 🌟 功能特色

-  **檔案上傳與驗證** - 支援 CSV、Excel 格式，即時驗證資料格式
-  **資料預覽與編輯** - 上傳後即時預覽，支援錯誤修正
-  **生產鏈追蹤** - P1→P2→P3 完整生產流程管理
-  **PostgreSQL 資料庫** - 高效能、可擴展的關聯式資料庫
-  **現代化介面** - 基於 Figma 設計系統的響應式介面
-  **Docker 容器化** - 一鍵啟動，環境隔離
-  **API 文檔** - 完整的 OpenAPI/Swagger 文檔

## 🏗️ 系統架構

```
表單分析系統
├── 前端 (React + TypeScript)
│   ├── 現代化 UI 元件庫
│   ├── 響應式設計
│   └── Figma 設計系統整合
├── 後端 (FastAPI + Python)
│   ├── 非同步 API 處理
│   ├── 資料驗證與轉換
│   └── 檔案處理服務
└── 資料庫 (PostgreSQL 16)
    ├── 擠出記錄 (P1)
    ├── 分條記錄 (P2)
    └── 沖孔記錄 (P3)
```

##  快速開始

### 前置需求

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 4.0+
- Windows 10/11 或 macOS 10.15+ 或 Ubuntu 18.04+
- 至少 4GB 可用記憶體

### 一鍵啟動

#### Windows 使用者

```batch
# 雙擊執行批次檔
start-system.bat

# 或使用 PowerShell
.\start-system.ps1
```

#### macOS/Linux 使用者

```bash
# 給予執行權限
chmod +x start-system.sh

# 執行啟動腳本
./start-system.sh
```

### 手動啟動

如果一鍵啟動遇到問題，可以使用手動方式：

```bash
# 1. 進入服務目錄
cd form-analysis-server

# 2. 啟動資料庫
docker-compose up -d db
sleep 15

# 3. 啟動後端服務
docker-compose up -d backend  
sleep 20

# 4. 啟動前端服務
docker-compose up -d frontend
sleep 15

# 5. 查看服務狀態
docker-compose ps
```

## 🔗 服務連結

啟動完成後，您可以訪問以下服務：

| 服務 | 網址 | 說明 |
|------|------|------|
| **前端應用** | http://localhost:5173 | 主要操作介面 |
| **API 文檔** | http://localhost:8000/docs | Swagger UI 文檔 |
| **API 替代文檔** | http://localhost:8000/redoc | ReDoc 文檔 |
| **資料庫管理** | http://localhost:5050 | pgAdmin (可選) |

##  專案結構

```
form-analysis-spec-kit/
├──  README.md                    # 專案說明文檔
├──  .env.example                 # 環境變數範例
├──  start-system.bat             # Windows 啟動腳本
├──  start-system.ps1             # PowerShell 啟動腳本
├── form-analysis-server/           # 主要服務目錄
│   ├── 🐳 docker-compose.yml       # 容器編排檔案
│   ├── backend/                    # 後端服務 (FastAPI)
│   │   ├── 🐳 Dockerfile           
│   │   ├──  requirements.txt     
│   │   ├── ⚙️ alembic.ini          # 資料庫遷移配置
│   │   ├── migrations/             # 資料庫遷移檔案
│   │   └── app/                    # 應用程式碼
│   │       ├── main.py             # FastAPI 應用入口
│   │       ├── core/               # 核心模組
│   │       │   ├── config.py       # 應用配置
│   │       │   └── database.py     # 資料庫連接
│   │       ├── models/             # 資料模型
│   │       ├── api/                # API 路由
│   │       └── services/           # 業務邏輯
│   └── frontend/                   # 前端應用 (React + TypeScript)
│       ├── 🐳 Dockerfile           
│       ├──  package.json         
│       ├── ⚡ vite.config.ts       
│       └── src/                    # 原始碼
│           ├── components/         # UI 元件
│           │   ├── ui/             # 基礎 UI 元件
│           │   └── layout/         # 版面配置
│           ├── pages/              # 頁面元件
│           ├── hooks/              # 自訂 Hooks
│           ├── lib/                # 工具函式庫
│           ├── types/              # TypeScript 類型
│           └── styles/             # 樣式檔案
└── docs/                           # 文檔目錄
    ├── API.md                      # API 使用說明
    ├── DEPLOYMENT.md               # 部署指南
    └── DEVELOPMENT.md              # 開發指南
```

##  開發指南

### 環境設定

1. **複製環境變數檔案**
   ```bash
   cp .env.example .env
   ```

2. **修改環境設定** (可選)
   ```bash
   # 資料庫連接
   DATABASE_URL=postgresql+asyncpg://app:app_secure_password@localhost:5432/form_analysis_db
   
   # API 服務
   API_HOST=0.0.0.0
   API_PORT=8000
   
   # 前端服務
   FRONTEND_PORT=5173
   ```

### 本地開發

#### 後端開發

```bash
cd form-analysis-server/backend

# 安裝虛擬環境
python -m venv venv
venv\Scripts\activate  # Windows
# 或 source venv/bin/activate  # macOS/Linux

# 安裝依賴
pip install -r requirements.txt

# 資料庫遷移
alembic upgrade head

# 啟動開發伺服器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 前端開發

```bash
cd form-analysis-server/frontend

# 安裝依賴
npm install

# 啟動開發伺服器
npm run dev
```

### 常用指令

```bash
# 查看服務狀態
docker-compose ps

# 查看服務日誌
docker-compose logs -f [service_name]

# 重啟特定服務
docker-compose restart [service_name]

# 停止所有服務
docker-compose down

# 完全清理（包含資料）
docker-compose down -v --remove-orphans
```

##  資料庫結構

系統使用 PostgreSQL 資料庫，主要資料表包括：

- **extrusion_records** - P1 擠出記錄
- **slitting_records** - P2 分條記錄  
- **slitting_checks** - P2 檢查記錄
- **punching_self_check_records** - P3 沖孔自檢記錄
- **uploaded_files** - 上傳檔案記錄
- **upload_audit** - 上傳審計日誌

詳細的資料庫 Schema 請參考：[API 文檔](http://localhost:8000/docs)

## 🔒 安全性設定

-  JWT 權杖認證 (準備中)
-  CORS 跨域保護
-  檔案類型驗證
-  檔案大小限制
-  SQL 注入防護
-  輸入資料驗證

##  API 使用範例

### 上傳檔案

```bash
curl -X POST "http://localhost:8000/api/upload/files" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@your_file.csv"
```

### 查詢 Lot 資料

```bash
curl -X GET "http://localhost:8000/api/view/lots?limit=10"
```

### 取得 P1 記錄

```bash
curl -X GET "http://localhost:8000/api/phase1/2503033_03"
```

更多 API 範例請參考：[Swagger 文檔](http://localhost:8000/docs)

## 🚨 故障排除

### 常見問題

#### 1. Docker 啟動失敗
```bash
# 檢查 Docker 服務狀態
docker --version
docker-compose --version

# 重啟 Docker Desktop
# Windows: 右鍵點擊系統匣圖示 → Restart
```

#### 2. 資料庫連接失敗
```bash
# 檢查資料庫容器狀態
docker-compose logs db

# 重啟資料庫服務
docker-compose restart db
```

#### 3. 前端無法訪問
```bash
# 檢查前端服務狀態
docker-compose logs frontend

# 確認端口是否被占用
netstat -an | findstr :5173
```

#### 4. 後端 API 錯誤
```bash
# 查看後端日誌
docker-compose logs backend

# 檢查環境變數配置
docker-compose config
```

### 清理重置

如果遇到嚴重問題，可以完全重置環境：

```bash
# 停止並移除所有容器
docker-compose down -v --remove-orphans

# 清理 Docker 映像檔（可選）
docker system prune -a

# 重新啟動
.\start-system.bat
```

## 🤝 貢獻指南

1. Fork 此專案
2. 建立功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交變更 (`git commit -m 'Add some amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 開啟 Pull Request

##  授權條款

此專案採用 MIT 授權條款。詳細內容請參考 [LICENSE](LICENSE) 檔案。

## 📞 聯絡資訊

- **專案維護者**: [Your Name]
- **電子郵件**: [your.email@example.com]
- **問題回報**: [GitHub Issues](https://github.com/your-repo/form-analysis-spec-kit/issues)

## 🎯 版本歷史

### v1.0.0 (2024-11-08)
- ✨ 初始版本發布
-  PostgreSQL 資料庫整合
-  現代化 React 前端
-  Docker 容器化部署
-  一鍵啟動腳本

---

<p align="center">
  Made with ❤️ for efficient form data processing
</p>