@echo off
REM PostgreSQL 本地開發環境啟動腳本
REM 此腳本啟動PostgreSQL Docker容器並初始化資料庫

echo.
echo ==========================================
echo    Form Analysis PostgreSQL 設置
echo ==========================================
echo.

echo 📊 正在啟動PostgreSQL Docker容器...
docker-compose up -d db

echo.
echo ⏳ 等待PostgreSQL準備就緒...
timeout /t 10 /nobreak > nul

echo.
echo 🔧 檢查PostgreSQL容器狀態...
docker-compose ps db

echo.
echo 📋 PostgreSQL連接資訊:
echo    主機: localhost
echo    端口: 5432  
echo    資料庫: form_analysis_db
echo    用戶: app
echo    密碼: app_secure_password

echo.
echo 🚀 正在初始化資料庫表格...
cd backend
python setup_postgresql.py
cd ..

echo.
echo ==========================================
echo ✅ PostgreSQL設置完成！
echo.
echo 💡 提示:
echo    - 使用 docker-compose logs db 查看資料庫日誌
echo    - 使用 docker-compose down 停止服務
echo    - 使用 docker-compose up -d pgadmin --profile tools 啟動pgAdmin
echo ==========================================

pause