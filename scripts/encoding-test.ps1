# Encoding Test Script
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Host "=== System Status Test ===" -ForegroundColor Green
Write-Host "Frontend: OK" -ForegroundColor Green
Write-Host "Backend: OK" -ForegroundColor Green
Write-Host "Database: OK" -ForegroundColor Green
Write-Host "Port 18001-18004: Available" -ForegroundColor Cyan
Write-Host "=== Test Complete ===" -ForegroundColor Green
