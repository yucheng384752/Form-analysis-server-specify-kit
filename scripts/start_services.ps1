# Form Analysis System - PowerShell 啟動腳本

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Form Analysis System - 啟動腳本" -ForegroundColor Cyan  
Write-Host "============================================" -ForegroundColor Cyan

# 檢查目錄是否存在
$backendDir = "C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\backend"
$frontendDir = "C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\frontend"

if (-not (Test-Path $backendDir)) {
    Write-Host " 後端目錄不存在: $backendDir" -ForegroundColor Red
    pause
    exit 1
}

if (-not (Test-Path $frontendDir)) {
    Write-Host " 前端目錄不存在: $frontendDir" -ForegroundColor Red
    pause
    exit 1
}

# 啟動後端服務
Write-Host " 正在啟動後端服務..." -ForegroundColor Green
$backendScript = @"
cd '$backendDir'
.\venv\Scripts\Activate.ps1
`$env:PYTHONPATH = '.'
python -c "import sys; sys.path.insert(0, '.'); from app.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8000)"
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendScript

# 等待後端啟動
Write-Host " 等待後端服務啟動..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 啟動前端服務  
Write-Host " 正在啟動前端服務..." -ForegroundColor Green
$frontendScript = @"
cd '$frontendDir'
npm run dev
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendScript

# 等待前端啟動
Write-Host " 等待前端服務啟動..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 打開瀏覽器
Write-Host "🌍 正在打開瀏覽器..." -ForegroundColor Green
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host " 服務啟動完成！" -ForegroundColor Green
Write-Host " 後端 API: http://localhost:8000" -ForegroundColor Cyan
Write-Host " 前端界面: http://localhost:5173" -ForegroundColor Cyan  
Write-Host " API 文檔: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "關閉此窗口將不會停止服務" -ForegroundColor Yellow
Write-Host "要停止服務，請關閉對應的 PowerShell 窗口" -ForegroundColor Yellow

# 測試服務連接
Write-Host ""
Write-Host "🧪 測試服務連接..." -ForegroundColor Magenta
Start-Sleep -Seconds 3

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host " 後端服務連接成功" -ForegroundColor Green
    }
} catch {
    Write-Host " 後端服務可能還在啟動中，請稍後手動檢查" -ForegroundColor Yellow
}

try {
    $response = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 5  
    if ($response.StatusCode -eq 200) {
        Write-Host " 前端服務連接成功" -ForegroundColor Green
    }
} catch {
    Write-Host " 前端服務可能還在啟動中，請稍後手動檢查" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎯 開始測試您的應用吧！" -ForegroundColor Green

pause