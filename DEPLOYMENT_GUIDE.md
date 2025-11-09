# 🚀 專案部署指南

本指南說明如何將 Form Analysis Spec Kit 專案打包並部署到另一台電腦。

## 📋 部署前檢查清單

### 🔍 當前電腦準備工作

#### 1. 清理專案（必做）
```bash
# 停止所有服務
.\scripts\stop-system.bat

# 清理 Docker 容器和映像（可選）
docker-compose down --volumes
docker system prune -f
```

#### 2. 檢查環境配置
- [ ] 確認 `.env` 檔案是否包含敏感資料
- [ ] 檢查資料庫中是否有重要資料需要備份
- [ ] 確認上傳檔案是否需要保留

#### 3. 創建乾淨的打包版本
```bash
# 移除不需要的檔案
rmdir /s /q .venv
rmdir /s /q __pycache__
rmdir /s /q node_modules
rmdir /s /q .vite
rmdir /s /q uploads
```

## 📦 打包方式

### 方式一：壓縮檔案（推薦）

1. **排除不必要的檔案**
   ```
   # 不要打包以下資料夾/檔案：
   - .venv/
   - __pycache__/
   - node_modules/
   - .vite/
   - uploads/（除非有重要檔案）
   - .git/（如果不需要版本記錄）
   ```

2. **打包命令**
   ```bash
   # 使用 7-Zip 或 WinRAR 打包整個資料夾
   # 或使用 PowerShell
   Compress-Archive -Path "c:\Users\Yucheng\Desktop\form-analysis-sepc-kit" -DestinationPath "form-analysis-kit.zip"
   ```

### 方式二：Git 倉庫（如果使用版本控制）

```bash
# 提交所有變更
git add .
git commit -m "Ready for deployment"

# 推送到遠端倉庫
git push origin main
```

## 🖥️ 目標電腦環境要求

### 必需軟體
- [ ] **Docker Desktop** (最新版本)
- [ ] **Docker Compose** (通常包含在 Docker Desktop 中)
- [ ] **Node.js** 18+ 
- [ ] **Python** 3.8+
- [ ] **Git** (如果使用 Git 部署)

### Windows 特定要求
- [ ] **PowerShell** 5.0+
- [ ] **Windows 10/11** (推薦)
- [ ] 啟用 **WSL2** (Docker Desktop 需要)

### 硬體要求
- [ ] **RAM**: 最少 4GB，推薦 8GB+
- [ ] **儲存空間**: 最少 2GB 可用空間
- [ ] **網路**: 穩定的網路連線（首次安裝需要下載 Docker 映像）

## 📋 部署步驟

### Step 1: 解壓縮專案
```bash
# 解壓到目標位置，例如：
C:\Projects\form-analysis-sepc-kit\
```

### Step 2: 環境配置
```bash
# 進入專案目錄
cd C:\Projects\form-analysis-sepc-kit

# 複製環境設定檔（如果需要）
copy .env.example .env
```

### Step 3: 檢查 Docker 服務
```bash
# 確認 Docker 正在運行
docker --version
docker-compose --version

# 測試 Docker 連線
docker run hello-world
```

### Step 4: 首次啟動
```bash
# 使用啟動腳本
.\scripts\start-system.bat

# 或手動啟動（如果腳本有問題）
cd form-analysis-server
docker-compose up -d --build
```

### Step 5: 驗證部署
- [ ] 前端: http://localhost:5173
- [ ] 後端 API: http://localhost:8000/docs
- [ ] 上傳測試檔案
- [ ] 查詢功能測試

## 🔧 常見問題排除

### Docker 相關問題

**問題**: Docker 無法啟動
```bash
# 解決方案：
1. 確認 Docker Desktop 正在運行
2. 重啟 Docker Desktop
3. 檢查 WSL2 是否正常
```

**問題**: 端口被佔用
```bash
# 檢查端口使用情況
netstat -ano | findstr :5173
netstat -ano | findstr :8000
netstat -ano | findstr :5432

# 終止佔用的程序
taskkill /PID <PID號碼> /F
```

### 建置問題

**問題**: Node.js 相依套件安裝失敗
```bash
# 進入前端目錄
cd form-analysis-server\frontend

# 清理並重新安裝
rmdir /s /q node_modules
del package-lock.json
npm install
```

**問題**: Python 相依套件問題
```bash
# 進入後端目錄
cd form-analysis-server\backend

# 建立虛擬環境
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 📁 檔案結構檢查

部署後確認以下結構存在：
```
form-analysis-sepc-kit/
├── docs/                    # ✅ 文檔
├── scripts/                 # ✅ 啟動腳本
├── test-data/              # ✅ 測試資料
├── form-analysis-server/   # ✅ 主應用
│   ├── backend/           # ✅ 後端代碼
│   ├── frontend/          # ✅ 前端代碼
│   └── docker-compose.yml # ✅ Docker 配置
├── README.md              # ✅ 說明文檔
└── .env.example          # ✅ 環境配置範例
```

## ⚡ 快速驗證腳本

創建一個快速驗證腳本來確認部署是否成功：

```batch
@echo off
echo "=== 專案部署驗證 ==="
echo.

echo "檢查 Docker..."
docker --version
if %errorlevel% neq 0 (
    echo "❌ Docker 未安裝或未運行"
    exit /b 1
)

echo "檢查專案結構..."
if not exist "scripts\start-system.bat" (
    echo "❌ 啟動腳本不存在"
    exit /b 1
)

if not exist "form-analysis-server\docker-compose.yml" (
    echo "❌ Docker Compose 檔案不存在"
    exit /b 1
)

echo "✅ 基本檢查通過"
echo "執行 .\scripts\start-system.bat 來啟動系統"
pause
```

## 📞 支援資訊

如果部署過程中遇到問題：

1. **檢查日誌檔案**:
   ```bash
   # Docker 容器日誌
   docker-compose logs backend
   docker-compose logs frontend
   ```

2. **系統診斷**:
   ```bash
   .\scripts\diagnose-system.bat
   ```

3. **重置環境**:
   ```bash
   .\scripts\stop-system.bat
   docker system prune -a --volumes
   .\scripts\start-system.bat
   ```

---
**部署指南版本**: 1.0  
**最後更新**: 2025年11月9日