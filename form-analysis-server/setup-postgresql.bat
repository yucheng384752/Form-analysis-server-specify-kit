@echo off
REM PostgreSQL 本地開發環境啟動腳本
REM 此腳本啟動PostgreSQL Docker容器並初始化資料庫

echo.
echo ==========================================
echo    Form Analysis PostgreSQL 設置
echo ==========================================
echo.

REM Compose v1/v2 偵測
set "DOCKER_COMPOSE=docker-compose"
docker-compose --version >nul 2>&1
if errorlevel 1 (
	docker compose --version >nul 2>&1
	if errorlevel 1 (
		echo Docker Compose 未安裝或不可用
		echo   請確認 Docker Desktop 已安裝 compose plugin 或已安裝 docker-compose
		pause
		exit /b 1
	) else (
		set "DOCKER_COMPOSE=docker compose"
	)
)

REM 讀取 host DB port（docker-compose 對外映射）
set "HOST_DB_PORT=18001"
if exist ".env" (
	for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"POSTGRES_PORT=" ".env"`) do (
		if not "%%b"=="" set "HOST_DB_PORT=%%b"
	)
)

echo  正在啟動PostgreSQL Docker容器...
%DOCKER_COMPOSE% up -d db

echo.
echo  等待PostgreSQL準備就緒...
timeout /t 10 /nobreak > nul

echo.
echo  檢查PostgreSQL容器狀態...
%DOCKER_COMPOSE% ps db

echo.
echo  PostgreSQL連接資訊:
echo    主機: localhost
echo    端口: !HOST_DB_PORT!
echo    資料庫: form_analysis_db
echo    用戶: app
echo    密碼: 請見 .env 的 POSTGRES_PASSWORD

echo.
echo  正在初始化資料庫表格...
cd backend
python setup_postgresql.py
cd ..

echo.
echo ==========================================
echo  PostgreSQL設置完成！
echo.
echo 提示:
echo    - 使用 %DOCKER_COMPOSE% logs db 查看資料庫日誌
echo    - 使用 %DOCKER_COMPOSE% down 停止服務
echo    - 使用 %DOCKER_COMPOSE% up -d pgadmin --profile tools 啟動pgAdmin
echo ==========================================

pause