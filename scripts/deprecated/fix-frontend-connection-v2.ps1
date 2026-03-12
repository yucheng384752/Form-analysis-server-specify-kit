# Form Analysis Frontend Connection Fix Script
# Set UTF-8 encoding for proper display
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding

Write-Host ""
Write-Host "=== Frontend Connection Fix ===" -ForegroundColor Green
Write-Host ""

# 1. Rebuild frontend container
Write-Host "[1] Rebuilding frontend container..." -ForegroundColor Yellow
Set-Location "form-analysis-server"
docker-compose build frontend
Write-Host "Frontend container rebuilt successfully" -ForegroundColor Green

Write-Host ""

# 2. Restart frontend service
Write-Host "[2] Restarting frontend service..." -ForegroundColor Yellow
docker-compose up -d frontend
Write-Host "Frontend service restarted" -ForegroundColor Green

Write-Host ""

# 3. Wait for service ready
Write-Host "[3] Waiting for service ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# 4. Test connections
Write-Host "[4] Testing frontend connections..." -ForegroundColor Yellow

$urls = @(
    "http://localhost:18003/",
    "http://localhost:18003/index.html"
)

foreach ($url in $urls) {
    Write-Host "Testing: $url" -NoNewline
    try {
        $response = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 5 -ErrorAction Stop
        Write-Host " -> SUCCESS ($($response.StatusCode))" -ForegroundColor Green
    } catch {
        Write-Host " -> FAILED" -ForegroundColor Red
    }
}

Write-Host ""

# 5. Check container status
Write-Host "[5] Checking container status..." -ForegroundColor Yellow
docker-compose ps

Write-Host ""

# 6. Show frontend logs
Write-Host "[6] Frontend logs summary..." -ForegroundColor Yellow
docker-compose logs --tail=10 frontend

Write-Host ""
Write-Host "=== Fix Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Recommended access URLs:" -ForegroundColor White
Write-Host "  Frontend App: http://localhost:18003/index.html" -ForegroundColor Cyan
Write-Host "  API Docs:     http://localhost:18002/docs" -ForegroundColor Cyan

# Ask if open browser
Write-Host ""
$openBrowser = Read-Host "Open frontend app in browser? (y/N)"
if ($openBrowser -eq 'y' -or $openBrowser -eq 'Y') {
    Start-Process "http://localhost:18003/index.html"
    Write-Host "Browser opened" -ForegroundColor Green
}