# 前端連接錯誤修復腳本
# 設置控制台編碼為 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding

Write-Host "=== 前端連接錯誤修復 ===" -ForegroundColor Green
Write-Host ""

# 1. 重新建構前端容器
Write-Host "[1] 重新建構前端容器..." -ForegroundColor Yellow
Set-Location "form-analysis-server"
docker-compose build frontend
Write-Host "前端容器重建完成" -ForegroundColor Green

Write-Host ""

# 2. 重新啟動前端服務
Write-Host "[2] 重新啟動前端服務..." -ForegroundColor Yellow
docker-compose up -d frontend
Write-Host "前端服務重新啟動" -ForegroundColor Green

Write-Host ""

# 3. 等待服務就緒
Write-Host "[3] 等待服務就緒..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# 4. 測試連接
Write-Host "[4] 測試前端連接..." -ForegroundColor Yellow

$urls = @(
    "http://localhost:18003/",
    "http://localhost:18003/index.html"
)

foreach ($url in $urls) {
    Write-Host "測試: $url" -NoNewline
    try {
        $response = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 5 -ErrorAction Stop
        Write-Host " -> ✅ 成功 ($($response.StatusCode))" -ForegroundColor Green
    } catch {
        Write-Host " -> ❌ 失敗" -ForegroundColor Red
    }
}

Write-Host ""

# 5. 檢查容器狀態
Write-Host "[5] 檢查容器狀態..." -ForegroundColor Yellow
docker-compose ps

Write-Host ""

# 6. 顯示日誌摘要
Write-Host "[6] 前端日誌摘要..." -ForegroundColor Yellow
docker-compose logs --tail=10 frontend

Write-Host ""
Write-Host "=== 修復完成 ===" -ForegroundColor Green
Write-Host ""
Write-Host "推薦訪問方式:" -ForegroundColor White
Write-Host "  前端應用: http://localhost:18003/index.html" -ForegroundColor Cyan
Write-Host "  API 文檔: http://localhost:18002/docs" -ForegroundColor Cyan

# 詢問是否開啟瀏覽器
Write-Host ""
$openBrowser = Read-Host "是否開啟前端應用? (y/N)"
if ($openBrowser -eq 'y' -or $openBrowser -eq 'Y') {
    Start-Process "http://localhost:18003/index.html"
    Write-Host "瀏覽器已開啟" -ForegroundColor Green
}