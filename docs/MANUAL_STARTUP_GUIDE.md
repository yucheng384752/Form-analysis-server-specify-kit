# Form Analysis System - 手動啟動指南

##  快速啟動步驟

### 步驟 1：啟動後端服務
1. 打開第一個 PowerShell 終端
2. 執行以下命令：
```powershell
cd "C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\backend"
.\venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
python -c "import sys; sys.path.insert(0, '.'); from app.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8000)"
```

### 步驟 2：啟動前端服務
1. 打開第二個 PowerShell 終端
2. 執行以下命令：
```powershell
cd "C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\frontend"
npm run dev
```

### 步驟 3：訪問應用
-  前端界面: http://localhost:5173
-  後端 API: http://localhost:8000
-  API 文檔: http://localhost:8000/docs

##  故障排除

### 如果後端啟動失敗：
1. 確保在正確的目錄：`C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\backend`
2. 確保虛擬環境已激活：`.\venv\Scripts\Activate.ps1`
3. 確保依賴已安裝：`pip install -r requirements.txt`
4. 確保資料庫已遷移：`alembic upgrade head`

### 如果前端啟動失敗：
1. 確保在正確的目錄：`C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\frontend`
2. 確保依賴已安裝：`npm install`
3. 如果端口被佔用，使用：`npm run dev -- --port 3001`

### 如果 Docker 想要使用：
1. 確保 Docker Desktop 正在運行
2. 等待 Docker Engine 完全啟動（通常需要 1-2 分鐘）
3. 然後再執行：`docker-compose up -d`

## 🎯 功能測試

### 測試上傳功能：
1. 訪問 http://localhost:5173
2. 拖放或選擇一個 CSV 文件
3. 查看驗證結果
4. 點擊匯入確認

### 測試 API：
1. 訪問 http://localhost:8000/docs
2. 測試 `/healthz` 端點
3. 測試 `/api/upload` 端點

##  系統狀態檢查

運行驗證腳本：
```powershell
python comprehensive_verification_test.py
```

這將檢查：
-  資料庫結構
-  API 端點
-  前端文件
-  配置文件

##  成功指標

看到以下輸出表示服務正常：

**後端成功啟動：**
```
 Form Analysis API starting on 0.0.0.0:8000
 Database: sqlite+aiosqlite:///./dev_test.db
 Upload limit: 10MB
🔒 CORS origins: ['http://localhost:5173', 'http://localhost:3000']
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

**前端成功啟動：**
```
VITE v4.5.14  ready in 267 ms
➜  Local:   http://localhost:5173/
➜  Network: http://192.168.x.x:5173/
```