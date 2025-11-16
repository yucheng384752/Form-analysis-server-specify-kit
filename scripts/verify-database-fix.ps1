# 資料庫欄位修復驗證腳本
# 設置控制台編碼為 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding

Write-Host ""
Write-Host "=== Database Field Fix Verification ===" -ForegroundColor Green
Write-Host ""

# 1. 檢查資料庫表結構
Write-Host "[1] Checking upload_jobs table structure..." -ForegroundColor Yellow
Set-Location "form-analysis-server"

$tableStructure = docker-compose exec db psql -U app -d form_analysis_db -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'upload_jobs' ORDER BY ordinal_position;" 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "Database table structure:" -ForegroundColor White
    Write-Host $tableStructure
    
    # 檢查 file_content 欄位是否存在
    if ($tableStructure -like "*file_content*") {
        Write-Host "✓ file_content field EXISTS in database" -ForegroundColor Green
    } else {
        Write-Host "✗ file_content field MISSING from database" -ForegroundColor Red
    }
} else {
    Write-Host "✗ Cannot connect to database" -ForegroundColor Red
}

Write-Host ""

# 2. 檢查 backend 服務狀態
Write-Host "[2] Checking backend service status..." -ForegroundColor Yellow
$backendStatus = docker-compose ps backend --format "{{.Status}}"

if ($backendStatus -like "*healthy*") {
    Write-Host "✓ Backend service is HEALTHY" -ForegroundColor Green
} else {
    Write-Host "⚠ Backend service status: $backendStatus" -ForegroundColor Yellow
}

Write-Host ""

# 3. 測試 API 連接
Write-Host "[3] Testing API connection..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:18002/docs" -Method Head -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✓ API documentation accessible (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "✗ API not accessible: $($_.Exception.Message)" -ForegroundColor Red
}

try {
    $response = Invoke-WebRequest -Uri "http://localhost:18002/health" -Method Get -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✓ API health check passed (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "⚠ API health endpoint not available" -ForegroundColor Yellow
}

Write-Host ""

# 4. 檢查前端連接
Write-Host "[4] Testing frontend connection..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:18003/index.html" -Method Head -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✓ Frontend accessible (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "✗ Frontend not accessible: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# 5. 顯示服務摘要
Write-Host "[5] Service Summary:" -ForegroundColor Yellow
docker-compose ps

Write-Host ""
Write-Host "=== Verification Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "1. Test file upload functionality in frontend" -ForegroundColor Cyan
Write-Host "2. Verify that the previous error no longer occurs" -ForegroundColor Cyan
Write-Host "3. Frontend URL: http://localhost:18003/index.html" -ForegroundColor Cyan

Write-Host ""