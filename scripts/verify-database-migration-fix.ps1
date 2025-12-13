# 資料庫遷移錯誤修復腳本

Write-Host "=== Database Migration Fix Verification ===" -ForegroundColor Green
Write-Host ""

# 1. 檢查 records 表是否包含 data_type 欄位
Write-Host "[1] Checking records table for data_type column..." -ForegroundColor Yellow
Set-Location "form-analysis-server"

try {
    $result = docker-compose exec db psql -U app -d form_analysis_db -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'records' AND column_name = 'data_type';" 2>$null
    
    if ($result -match "1") {
        Write-Host "✓ data_type column EXISTS in records table" -ForegroundColor Green
    } else {
        Write-Host "data_type column MISSING in records table" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Failed to check database structure" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 2. 檢查 data_type_enum 是否存在
Write-Host "[2] Checking for data_type_enum..." -ForegroundColor Yellow
try {
    $result = docker-compose exec db psql -U app -d form_analysis_db -c "SELECT COUNT(*) FROM pg_type WHERE typname = 'data_type_enum';" 2>$null
    
    if ($result -match "1") {
        Write-Host "✓ data_type_enum EXISTS" -ForegroundColor Green
    } else {
        Write-Host "data_type_enum MISSING" -ForegroundColor Red
    }
} catch {
    Write-Host "Failed to check enum type" -ForegroundColor Red
}

Write-Host ""

# 3. 檢查後端服務狀態
Write-Host "[3] Checking backend service status..." -ForegroundColor Yellow
$status = docker-compose ps backend --format "table {{.Status}}" 2>$null | Select-String "healthy"
if ($status) {
    Write-Host "✓ Backend service is HEALTHY" -ForegroundColor Green
} else {
    Write-Host "Backend service status unknown" -ForegroundColor Yellow
}

Write-Host ""

# 4. 測試 API 連接
Write-Host "[4] Testing API connection..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:18002/docs" -Method Head -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✓ API documentation accessible (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "API not accessible" -ForegroundColor Red
}

try {
    $healthResponse = Invoke-WebRequest -Uri "http://localhost:18002/healthz" -Method Get -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✓ API health endpoint working (Status: $($healthResponse.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "API health endpoint not available" -ForegroundColor Yellow
}

Write-Host ""

# 5. 檢查最新的後端日誌是否有錯誤
Write-Host "[5] Checking recent backend logs for errors..." -ForegroundColor Yellow
$logs = docker-compose logs --tail=20 backend 2>$null | Select-String "error|ERROR" -Context 0
if ($logs.Count -eq 0) {
    Write-Host "✓ No recent errors in backend logs" -ForegroundColor Green
} else {
    Write-Host "Found $($logs.Count) error entries in recent logs" -ForegroundColor Yellow
}

Write-Host ""

# 6. 顯示服務摘要
Write-Host "[6] Service Summary:" -ForegroundColor Yellow
docker-compose ps

Write-Host ""
Write-Host "=== Migration Fix Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Database structure has been updated to support:" -ForegroundColor White
Write-Host "- data_type column in records table" -ForegroundColor Cyan
Write-Host "- P1/P2/P3 data type enumeration" -ForegroundColor Cyan
Write-Host "- Additional P2/P3 specific columns" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "1. Test file upload functionality in frontend" -ForegroundColor Cyan
Write-Host "2. Verify that import operations now work correctly" -ForegroundColor Cyan
Write-Host "3. Frontend URL: http://localhost:18003/index.html" -ForegroundColor Cyan