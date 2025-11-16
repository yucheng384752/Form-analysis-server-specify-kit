# Frontend Connection Diagnostic Script
Write-Host "=== 前端連接診斷腳本 ===" -ForegroundColor Blue
Write-Host ""

# Test 1: Check container status
Write-Host "[1] 檢查容器狀態..." -ForegroundColor Yellow
docker-compose ps | Select-String "frontend"

Write-Host ""

# Test 2: Check port mapping
Write-Host "[2] 檢查端口映射..." -ForegroundColor Yellow
docker port form_analysis_frontend

Write-Host ""

# Test 3: Test internal container access
Write-Host "[3] 測試容器內部訪問..." -ForegroundColor Yellow
$internalTest = docker exec form_analysis_frontend curl -s -w "Status:%{http_code}" -o /dev/null http://localhost:5173/
Write-Host "內部訪問結果: $internalTest"

Write-Host ""

# Test 4: Test different external URLs
Write-Host "[4] 測試外部訪問..." -ForegroundColor Yellow

$urls = @(
    "http://localhost:18003/",
    "http://127.0.0.1:18003/",
    "http://localhost:18003/index.html",
    "http://127.0.0.1:18003/index.html"
)

foreach ($url in $urls) {
    try {
        Write-Host "測試: $url" -NoNewline
        $response = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 3 -ErrorAction Stop
        Write-Host " -> 成功 ($($response.StatusCode))" -ForegroundColor Green
    } catch {
        Write-Host " -> 失敗: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""

# Test 5: Check network connectivity
Write-Host "[5] 檢查網絡連接..." -ForegroundColor Yellow
$netTest = Test-NetConnection localhost -Port 18003 -InformationLevel Quiet
Write-Host "端口 18003 連通性: $(if ($netTest) {'成功'} else {'失敗'})"

Write-Host ""

# Test 6: Check Docker logs
Write-Host "[6] 檢查前端日誌 (最後 10 行)..." -ForegroundColor Yellow
docker-compose logs --tail=10 frontend

Write-Host ""
Write-Host "=== 診斷完成 ===" -ForegroundColor Blue