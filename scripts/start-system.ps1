# 表單分析系統 - PowerShell 啟動腳本
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "     表單分析系統 - 一鍵啟動腳本" -ForegroundColor Green  
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# 設置執行政策（如果需要）
try {
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction SilentlyContinue
} catch {
    # 忽略權限錯誤
}

# 設置工作目錄
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# 檢查 Docker 服務
Write-Host "[1/5] 檢查 Docker 服務狀態..." -ForegroundColor Yellow
try {
    docker --version | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " Docker 服務正常" -ForegroundColor Green
    } else {
        throw "Docker 未正常運行"
    }
} catch {
    Write-Host " Docker 未安裝或未啟動" -ForegroundColor Red
    Write-Host "   請安裝 Docker Desktop 並確保服務正在運行" -ForegroundColor Red
    Read-Host "按 Enter 繼續"
    exit 1
}

# 檢查 docker-compose 檔案
if (!(Test-Path "form-analysis-server\docker-compose.yml")) {
    Write-Host " 找不到 docker-compose.yml 檔案" -ForegroundColor Red
    Write-Host "   請確認您在專案根目錄執行此腳本" -ForegroundColor Red
    Read-Host "按 Enter 繼續"
    exit 1
}

Write-Host ""
Write-Host "[2/5] 停止現有容器並清理..." -ForegroundColor Yellow
Set-Location "form-analysis-server"
docker-compose down --remove-orphans | Out-Null

Write-Host ""
Write-Host "[3/5] 啟動 PostgreSQL 資料庫..." -ForegroundColor Yellow
docker-compose up -d db | Out-Null
Write-Host "    等待資料庫初始化 (15秒)..." -ForegroundColor Cyan
Start-Sleep -Seconds 15

Write-Host ""
Write-Host "[4/5] 啟動後端 API 服務..." -ForegroundColor Yellow  
docker-compose up -d backend | Out-Null
Write-Host "    等待 API 服務啟動 (20秒)..." -ForegroundColor Cyan
Start-Sleep -Seconds 20

Write-Host ""
Write-Host "[5/5] 啟動前端應用..." -ForegroundColor Yellow
docker-compose up -d frontend | Out-Null
Write-Host "    等待前端服務啟動 (15秒)..." -ForegroundColor Cyan
Start-Sleep -Seconds 15

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "             啟動完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host " 服務連結：" -ForegroundColor White
Write-Host "   前端應用: " -NoNewline -ForegroundColor White
Write-Host "http://localhost:5173" -ForegroundColor Cyan
Write-Host "   API 文檔: " -NoNewline -ForegroundColor White  
Write-Host "http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "   資料庫管理: " -NoNewline -ForegroundColor White
Write-Host "http://localhost:5050 (可選)" -ForegroundColor Cyan

Write-Host ""
Write-Host " 檢查服務狀態：" -ForegroundColor White
docker-compose ps

Write-Host ""
Write-Host " 常用指令：" -ForegroundColor White
Write-Host "   查看日誌: docker-compose logs -f" -ForegroundColor Gray
Write-Host "   停止服務: docker-compose down" -ForegroundColor Gray
Write-Host "   重啟服務: docker-compose restart" -ForegroundColor Gray

Write-Host ""
$openBrowser = Read-Host "是否開啟前端應用？(y/N)"
if ($openBrowser -eq 'y' -or $openBrowser -eq 'Y') {
    Start-Process "http://localhost:5173"
}