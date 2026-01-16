# Form Analysis Server

一個基於 FastAPI 和 React 的檔案上傳、驗證與分析系統。支援 CSV 和 Excel 檔案的上傳、即時驗證、錯誤報告和資料匯入功能。

## 主要功能

-  **檔案上傳**: 支援 CSV 和 Excel (.xlsx) 格式，最大 10MB（不支援 .xls）
-  **即時驗證**: 格式和內容驗證，即時錯誤回報
-  **資料預覽**: 可預覽匯入資料，錯誤高亮顯示
-  **批次匯入**: 交易安全的批量資料匯入
-  **錯誤匯出**: 下載錯誤資料為 CSV 以便修正
-  **健康監控**: 完整的健康檢查和監控

##  系統架構

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (React+Vite)  │◄──►│   (FastAPI)     │◄──►│   (PostgreSQL)  │
│   Port: 18003   │    │   Port: 18002   │    │   Port: 18001   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

##  快速開始（Docker）

### 前提條件

- [Docker Desktop](https://www.docker.com/products/docker-desktop) 已安裝並運行
- [curl](https://curl.se/download.html) 已安裝（用於 API 測試）
- 可用埠口：18003（前端）、18002（後端）、18001（資料庫）

### 一鍵啟動

注意：目前 Docker Compose 的後端服務在「部署層」預設啟用 `AUTH_MODE=api_key`（用來阻擋公網掃描/濫用）。

- 使用 `quick-start.ps1/.bat/.sh`：腳本會在需要時自動 bootstrap 一把測試用 API key，並在輸出中顯示（只顯示一次，請保存）。
- 手動啟動 `docker compose up -d`：請參考後端文件建立第一把 key（[backend/README.md](backend/README.md) 的「建立第一把 key（bootstrap）」）。

**Windows (PowerShell)**
```powershell
# 完整啟動和測試
.\quick-start.ps1

# 只啟動服務，跳過測試
.\quick-start.ps1 -SkipTests

# (可選，會清空 DB) 移除 Docker volumes
.\quick-start.ps1 -ResetDb
```

**Windows (命令提示字元)**
```cmd
quick-start.bat

REM (可選，會清空 DB) 移除 Docker volumes
quick-start.bat --reset-db
```

**Linux/macOS**
```bash
chmod +x quick-start.sh
./quick-start.sh

# (可選，會清空 DB) 移除 Docker volumes
./quick-start.sh --reset-db
```

### 保留資料庫資料的啟動方式（建議）

如果你希望重啟系統時保留 PostgreSQL 內的資料，請使用專案根目錄的啟動腳本：

- `scripts/start-system.ps1`
- `scripts/start-system.bat`

它們會停止容器並重新啟動，但不會移除 volumes（因此不會清空 DB）。

### 手動啟動步驟

1. **啟動所有服務**
   ```bash
   docker compose up -d
   ```

2. **驗證健康檢查**
   ```bash
   # 基本健康檢查
   curl -f http://localhost:18002/healthz
   
   # 詳細健康檢查（包含資料庫連接）
   curl -f http://localhost:18002/healthz/detailed
   ```

3. **模擬上傳與驗證流程**
   
   創建測試 CSV 檔案：
   ```bash
   cat << 'EOF' > test_upload.csv
   lot_no,product_name,quantity,production_date
   1234567_01,測試產品A,100,2024-01-15
   2345678_02,測試產品B,50,2024-01-16
   3456789_03,測試產品C,75,2024-01-17
   4567890_04,測試產品D,200,2024-01-18
   5678901_05,測試產品E,125,2024-01-19
   EOF
   ```
   
   上傳檔案：
   ```bash
      # 上傳檔案
      # 注意：若你使用 Docker Compose 預設設定（AUTH_MODE=api_key），所有 /api/* 請求都需要帶 API key。
      curl -X POST \
         -H "X-API-Key: <YOUR_API_KEY>" \
         -F "file=@test_upload.csv" \
         http://localhost:18002/api/upload
   
   # 範例回應:
   # {
   #   "file_id": "abc123def456",
   #   "filename": "test_upload.csv",
   #   "status": "validated",
   #   "message": "File uploaded and validated successfully"
   # }
   
   # 如果有錯誤，下載錯誤報告（使用上傳回應中的 file_id）
      curl -H "X-API-Key: <YOUR_API_KEY>" \
         "http://localhost:18002/api/errors.csv?file_id=abc123def456"
   
   # 確認匯入資料（使用上傳回應中的 file_id）
      curl -X POST \
         -H "X-API-Key: <YOUR_API_KEY>" \
         -H "Content-Type: application/json" \
        -d '{"file_id":"abc123def456"}' \
        http://localhost:18002/api/import
   ```

4. **訪問前端應用**
   
   開啟瀏覽器訪問：http://localhost:18003

##  環境配置

### API Base URL 設定

在 `.env` 檔案中配置前端 API 端點：

```env
# 前端配置
VITE_API_URL=http://localhost:18002
VITE_MAX_FILE_SIZE=10485760  # 10MB in bytes

# 後端 CORS 設定
CORS_ORIGINS=http://localhost:18003,http://localhost:3000
```

### 資料庫驅動選擇

選擇合適的 PostgreSQL 驅動程式取決於您的應用程式配置：

- **asyncpg** - 建議用於本地開發和非同步 FastAPI 應用
  ```env
  DATABASE_URL=postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db
  ```

- **psycopg** - 用於 Docker 環境（支援同步和非同步模式）
  ```env
  DATABASE_URL=postgresql+psycopg://app:app_secure_password_2024@db:5432/form_analysis_db
  ```

### vite.config.ts 代理設定

前端已配置 API 代理，支援開發模式下的跨域請求：

```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:18002',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
```

### CORS 配置確認

後端已配置 CORS 中間件，支援以下來源：
- http://localhost:18003 （Vite 開發伺服器 - 主要前端埠）
- http://localhost:3000 （備用前端埠，兼容性保留）

如需添加其他來源，請修改 `.env` 檔案中的 `CORS_ORIGINS`。

##  API 文件

啟動服務後，可訪問以下 API 文件：

- **Swagger UI**: http://localhost:18002/docs
- **ReDoc**: http://localhost:18002/redoc
- **OpenAPI JSON**: http://localhost:18002/openapi.json

### 主要 API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/upload` | POST | 檔案上傳和驗證 |
| `/api/errors.csv` | GET | 下載錯誤報告 |
| `/api/import` | POST | 確認資料匯入 |
| `/healthz` | GET | 基本健康檢查 |
| `/healthz/detailed` | GET | 詳細健康檢查 |

## 常見問題

### 檔案上傳問題

**Q: 上傳失敗，提示檔案過大**
A: 檢查以下設定：
- 前端限制：`.env` 中的 `VITE_MAX_FILE_SIZE`
- 後端限制：`.env` 中的 `MAX_UPLOAD_SIZE_MB`
- 預設限制為 10MB

**Q: 支援哪些檔案格式？**
A: 
- CSV 檔案（UTF-8 編碼，支援 BOM）
- Excel 檔案（.xlsx 格式）
- 不支援 .xls（舊版 Excel）格式

### Windows 權限問題

**Q: PowerShell 提示「無法載入腳本」**
A: 執行下列命令設定執行政策：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Q: Docker 權限錯誤**
A: 確保：
- Docker Desktop 已啟動
- 使用者帳戶在 docker-users 群組中
- 如使用 WSL2，確保 WSL 整合已啟用

### CORS 錯誤

**Q: 前端請求被 CORS 政策阻擋**
A: 檢查以下配置：
1. 後端 `.env` 檔案中的 `CORS_ORIGINS` 包含前端網址
2. 確認前端使用正確的 API Base URL
3. 開發模式下確保 vite.config.ts 代理設定正確

**Q: API 請求 404 錯誤**
A: 確認：
- 後端服務正常運行（http://localhost:18002/docs）
- API Base URL 配置正確
- 網路連線正常

### 資料庫連接問題

**Q: 資料庫連接失敗**
A: 檢查：
```bash
# 檢查資料庫容器狀態
docker compose ps

# 檢查資料庫日誌
docker compose logs db

# 測試資料庫連接
docker compose exec db pg_isready -U app
```

**Q: 資料持久化問題**
A: 資料庫資料存儲在 Docker Volume 中：
```bash
# 檢視 volumes
docker volume ls

# 清理所有資料（注意：會刪除所有資料）
docker compose down -v
```

##  偵錯指南

### 檢視服務日誌

```bash
# 所有服務日誌
docker compose logs -f

# 特定服務日誌
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db
```

### 服務狀態檢查

```bash
# 檢查容器狀態
docker compose ps

# 檢查服務健康狀態
curl http://localhost:18002/healthz

# 檢查前端可訪問性
curl http://localhost:18003
```

### 重新啟動服務

```bash
# 重新啟動所有服務
docker compose restart

# 重新啟動特定服務
docker compose restart backend

# 完全重建和啟動
docker compose down
docker compose up -d --build
```

##  開發指南

### 本地開發環境

如果您想要在本地開發環境中運行（不使用 Docker）：

1. **後端開發**
   ```bash
   cd backend
   pip install -e .[dev]
   python app/main.py
   ```

2. **前端開發**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **資料庫設置**
   ```bash
   # 使用 Docker 運行 PostgreSQL
   docker run -d --name postgres \
     -e POSTGRES_USER=app \
     -e POSTGRES_PASSWORD=app_secure_password_2024 \
     -e POSTGRES_DB=form_analysis_db \
     -p 5432:5432 postgres:16
   ```

### 測試

```bash
# 後端測試
cd backend
pytest

# 前端測試  
cd frontend
npm test

# 整合測試
python backend/tests/test_integration.py
```

##  生產部署

在生產環境中部署時，請注意：

1. **更改預設密碼和金鑰**
   ```env
   SECRET_KEY=your-secure-random-key-here
   POSTGRES_PASSWORD=your-secure-password-here
   ```

2. **使用生產配置**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

3. **設定反向代理**（如使用 Nginx）

4. **啟用 HTTPS**

5. **配置監控和日誌收集**

##  授權

本專案採用 MIT 授權條款。

##  貢獻

歡迎提交問題和拉取請求！請確保：

1. 程式碼符合專案風格
2. 添加適當的測試
3. 更新相關文件
4. 確保所有測試通過

## 支援

如有問題或建議，請：

1. 查看本文件的常見問題章節
2. 在 GitHub 上提交 Issue
3. 檢查現有的 Issue 和 PR

---

**快樂編程！** 