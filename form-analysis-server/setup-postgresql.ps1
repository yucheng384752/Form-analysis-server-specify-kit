# PostgreSQL 本地開發環境啟動腳本
# 此腳本啟動PostgreSQL Docker容器並初始化資料庫

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   Form Analysis PostgreSQL 設置" -ForegroundColor Cyan  
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host " 正在啟動PostgreSQL Docker容器..." -ForegroundColor Yellow
docker-compose up -d db

Write-Host ""
Write-Host " 等待PostgreSQL準備就緒..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host ""
Write-Host " 檢查PostgreSQL容器狀態..." -ForegroundColor Yellow
docker-compose ps db

Write-Host ""
Write-Host " PostgreSQL連接資訊:" -ForegroundColor Green
Write-Host "   主機: localhost" -ForegroundColor White
Write-Host "   端口: 5432" -ForegroundColor White
Write-Host "   資料庫: form_analysis_db" -ForegroundColor White
Write-Host "   用戶: app" -ForegroundColor White
Write-Host "   密碼: app_secure_password" -ForegroundColor White

Write-Host ""
Write-Host " 正在初始化資料庫表格..." -ForegroundColor Yellow
Push-Location backend
python setup_postgresql.py
Pop-Location

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " PostgreSQL設置完成！" -ForegroundColor Green
Write-Host ""
Write-Host "提示:" -ForegroundColor Yellow
Write-Host "   - 使用 docker-compose logs db 查看資料庫日誌" -ForegroundColor White
Write-Host "   - 使用 docker-compose down 停止服務" -ForegroundColor White  
Write-Host "   - 使用 docker-compose up -d pgadmin --profile tools 啟動pgAdmin" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan

Read-Host "按Enter鍵繼續"