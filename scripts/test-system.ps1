# Form Analysis System Test Script
Write-Host ""
Write-Host "========================================" -ForegroundColor Blue
Write-Host "     Form Analysis System Test Suite" -ForegroundColor Blue  
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""

# Change to form-analysis-server directory
Set-Location "form-analysis-server"

# Test Results
$testResults = @()

# Test 1: Container Status
Write-Host "[TEST 1] Container Status Check" -ForegroundColor Yellow
$containerStatus = docker-compose ps --format "table {{.Name}}\t{{.Status}}"
Write-Host $containerStatus
$runningContainers = (docker-compose ps -q | Measure-Object).Count
if ($runningContainers -eq 3) {
    $testResults += @{Test="Container Status"; Result="PASS"; Details="All 3 containers running"}
    Write-Host "✓ PASS - All containers running" -ForegroundColor Green
} else {
    $testResults += @{Test="Container Status"; Result="FAIL"; Details="Expected 3 containers, found $runningContainers"}
    Write-Host "✗ FAIL - Expected 3 containers, found $runningContainers" -ForegroundColor Red
}

Write-Host ""

# Test 2: Database Connection
Write-Host "[TEST 2] Database Connection" -ForegroundColor Yellow
try {
    $dbTest = docker exec form_analysis_db psql -U app -d form_analysis_db -c "SELECT 1;" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $testResults += @{Test="Database Connection"; Result="PASS"; Details="PostgreSQL responding on port 18001"}
        Write-Host "✓ PASS - Database connection successful" -ForegroundColor Green
    } else {
        throw "Database connection failed"
    }
} catch {
    $testResults += @{Test="Database Connection"; Result="FAIL"; Details=$_.Exception.Message}
    Write-Host "✗ FAIL - Database connection failed" -ForegroundColor Red
}

Write-Host ""

# Test 3: API Health Check
Write-Host "[TEST 3] API Health Check" -ForegroundColor Yellow
try {
    $apiResponse = Invoke-WebRequest -Uri "http://localhost:18002/healthz" -Method Get -TimeoutSec 10
    if ($apiResponse.StatusCode -eq 200) {
        $apiContent = $apiResponse.Content | ConvertFrom-Json
        $testResults += @{Test="API Health"; Result="PASS"; Details="API responding with status: $($apiContent.status)"}
        Write-Host "✓ PASS - API health check successful (Status: $($apiContent.status))" -ForegroundColor Green
    } else {
        throw "API returned status code $($apiResponse.StatusCode)"
    }
} catch {
    $testResults += @{Test="API Health"; Result="FAIL"; Details=$_.Exception.Message}
    Write-Host "✗ FAIL - API health check failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# Test 4: API Documentation
Write-Host "[TEST 4] API Documentation" -ForegroundColor Yellow
try {
    $docsResponse = Invoke-WebRequest -Uri "http://localhost:18002/docs" -Method Head -TimeoutSec 10
    if ($docsResponse.StatusCode -eq 200) {
        $testResults += @{Test="API Docs"; Result="PASS"; Details="Swagger UI accessible on port 18002"}
        Write-Host "✓ PASS - API documentation accessible" -ForegroundColor Green
    } else {
        throw "API docs returned status code $($docsResponse.StatusCode)"
    }
} catch {
    $testResults += @{Test="API Docs"; Result="FAIL"; Details=$_.Exception.Message}
    Write-Host "✗ FAIL - API documentation failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# Test 5: Frontend Container Internal Check
Write-Host "[TEST 5] Frontend Service" -ForegroundColor Yellow
try {
    $frontendTest = docker exec form_analysis_frontend curl -s -I http://localhost:5173/ 2>&1
    if ($frontendTest -like "*200 OK*") {
        $testResults += @{Test="Frontend Service"; Result="PASS"; Details="Vite dev server running internally"}
        Write-Host "✓ PASS - Frontend service running internally" -ForegroundColor Green
    } else {
        throw "Frontend internal check failed"
    }
} catch {
    $testResults += @{Test="Frontend Service"; Result="FAIL"; Details=$_.Exception.Message}
    Write-Host "✗ FAIL - Frontend service check failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# Test 6: Port Availability Check
Write-Host "[TEST 6] Port Configuration" -ForegroundColor Yellow
$ports = @(18001, 18002, 18003)
$portResults = @()
foreach ($port in $ports) {
    $portTest = Test-NetConnection localhost -Port $port -WarningAction SilentlyContinue
    if ($portTest.TcpTestSucceeded) {
        $portResults += "Port ${port}: OPEN"
    } else {
        $portResults += "Port ${port}: CLOSED"
    }
}
$testResults += @{Test="Port Configuration"; Result="INFO"; Details=($portResults -join ", ")}
Write-Host "Port Status: $($portResults -join ' | ')" -ForegroundColor Cyan

Write-Host ""

# Test Summary
Write-Host "========================================" -ForegroundColor Blue
Write-Host "           TEST SUMMARY" -ForegroundColor Blue
Write-Host "========================================" -ForegroundColor Blue

$passCount = ($testResults | Where-Object {$_.Result -eq "PASS"}).Count
$failCount = ($testResults | Where-Object {$_.Result -eq "FAIL"}).Count
$totalTests = $passCount + $failCount

foreach ($result in $testResults) {
    $color = switch ($result.Result) {
        "PASS" { "Green" }
        "FAIL" { "Red" }
        "INFO" { "Cyan" }
    }
    Write-Host "$($result.Test): $($result.Result) - $($result.Details)" -ForegroundColor $color
}

Write-Host ""
Write-Host "Overall Result: $passCount/$totalTests tests passed" -ForegroundColor $(if ($failCount -eq 0) {"Green"} else {"Yellow"})

if ($failCount -eq 0) {
    Write-Host "🎉 All core services are working correctly!" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some issues detected. Please review the failed tests." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Service URLs:" -ForegroundColor White
Write-Host "  Frontend: http://localhost:18003" -ForegroundColor Cyan
Write-Host "  API Docs: http://localhost:18002/docs" -ForegroundColor Cyan  
Write-Host "  API Health: http://localhost:18002/healthz" -ForegroundColor Cyan
Write-Host "  Database: localhost:18001 (PostgreSQL)" -ForegroundColor Cyan