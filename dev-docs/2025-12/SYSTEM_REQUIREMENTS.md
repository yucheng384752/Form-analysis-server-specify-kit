# 系統需求檢查清單

在部署 Form Analysis Spec Kit 到新電腦前，請確認以下軟體已安裝：

##  必需軟體

### Docker & 容器化
- [ ] **Docker Desktop** (最新版本)
  - 下載：https://www.docker.com/products/docker-desktop/
  - Windows 需求：Windows 10/11 Pro, Enterprise, or Education
  - 需要啟用 WSL2

### 開發環境
- [ ] **Node.js** 18.0+ 
  - 下載：https://nodejs.org/
  - 驗證：`node --version`
  - 包含 npm 套件管理器

- [ ] **Python** 3.8+
  - 下載：https://www.python.org/
  - 驗證：`python --version`
  - 建議使用 Python 3.11

### 版本控制（可選）
- [ ] **Git**
  - 下載：https://git-scm.com/
  - 驗證：`git --version`

##  快速檢查命令

在新電腦上執行以下命令檢查環境：

```bash
# 檢查 Docker
docker --version
docker-compose --version

# 檢查 Node.js 
node --version
npm --version

# 檢查 Python
python --version
pip --version

# 檢查 Git（可選）
git --version
```

##  一鍵安裝腳本

### Windows (使用 Chocolatey)
```powershell
# 安裝 Chocolatey（如果未安裝）
Set-ExecutionPolicy Bypass -Scope Process -Force
iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

# 安裝所有必需軟體
choco install docker-desktop nodejs python git -y
```

### Windows (使用 Winget)
```bash
# 安裝 Docker Desktop
winget install Docker.DockerDesktop

# 安裝 Node.js
winget install OpenJS.NodeJS

# 安裝 Python  
winget install Python.Python.3.11

# 安裝 Git
winget install Git.Git
```

## 💾 硬體需求

- **RAM**: 最少 4GB，建議 8GB+
- **CPU**: 2核心以上（Docker 需要）
- **儲存空間**: 最少 5GB 可用空間
- **網路**: 穩定的網路連線

## 🔐 權限需求

### Windows
- 管理員權限（安裝軟體時）
- 啟用 WSL2 功能
- 啟用 Hyper-V（Docker 需要）

### 防火牆設定
確認以下端口可以使用：
- `5173` - 前端應用
- `8000` - 後端 API
- `5432` - PostgreSQL 資料庫

##  部署檢查清單

部署前請確認：

1. **軟體安裝**
   - [ ] Docker Desktop 執行正常
   - [ ] Node.js 版本 18+
   - [ ] Python 版本 3.8+

2. **專案檔案**
   - [ ] 已解壓縮專案檔案
   - [ ] 確認資料夾結構完整
   - [ ] 執行 `verify-deployment.bat`

3. **首次啟動**
   - [ ] 執行 `scripts\start-system.bat`
   - [ ] 等待所有服務啟動
   - [ ] 開啟瀏覽器測試

4. **功能驗證**
   - [ ] 前端載入正常 (http://localhost:5173)
   - [ ] API 文檔可存取 (http://localhost:8000/docs)
   - [ ] 上傳測試檔案成功
   - [ ] 查詢功能正常

## 故障排除

### 常見問題

**Docker 無法啟動**
- 確認 WSL2 已安裝並啟用
- 重啟 Docker Desktop
- 檢查系統是否支援虛擬化

**端口被佔用**
- 檢查：`netstat -ano | findstr :5173`
- 終止程序：`taskkill /PID <PID> /F`

**權限問題**
- 以管理員身分執行
- 檢查防火牆設定
- 確認 Docker 權限

---

**最後更新**: 2025年11月9日