# 編碼測試腳本
# 設置控制台編碼為 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding

Write-Host ""
Write-Host "=== 中文編碼測試 ===" -ForegroundColor Green
Write-Host ""

Write-Host "測試項目：" -ForegroundColor Yellow
Write-Host "✅ 前端連接正常" -ForegroundColor Green
Write-Host "✅ 後端API運行" -ForegroundColor Green  
Write-Host "✅ 資料庫連接" -ForegroundColor Green
Write-Host "❌ 根路徑需要修復" -ForegroundColor Red

Write-Host ""
Write-Host "Port配置：" -ForegroundColor Cyan
Write-Host "  資料庫: 18001" -ForegroundColor White
Write-Host "  API: 18002" -ForegroundColor White
Write-Host "  前端: 18003" -ForegroundColor White
Write-Host "  管理: 18004" -ForegroundColor White

Write-Host ""
Write-Host "=== 測試完成 ===" -ForegroundColor Green
Write-Host ""