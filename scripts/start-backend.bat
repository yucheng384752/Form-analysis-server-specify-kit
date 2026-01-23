@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
echo.
echo ========================================
echo     表單分析系統 - 單獨啟動後端
echo ========================================
echo.

cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

if not exist "%SERVER_PATH%\docker-compose.yml" (
    echo 找不到 docker-compose.yml: %SERVER_PATH%\docker-compose.yml
    pause
    exit /b 1
)

docker --version >nul 2>&1
if errorlevel 1 (
    echo Docker 未安裝或未啟動，請先啟動 Docker Desktop
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo docker-compose 不可用，請確認 Docker Compose 已安裝
    pause
    exit /b 1
)

set "HOST_API_PORT=18002"
if exist "%SERVER_PATH%\.env" (
    for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"API_PORT=" "%SERVER_PATH%\.env"`) do (
        if not "%%b"=="" set "HOST_API_PORT=%%b"
    )
)

echo [1/2] 啟動 db + backend...
cd /d "%SERVER_PATH%"
docker-compose up -d db backend
if errorlevel 1 (
    echo 啟動失敗，請查看日誌：
    echo   monitor_backend.bat
    pause
    exit /b 1
)

echo.
echo [2/2] 完成
echo 後端 URL: http://localhost:!HOST_API_PORT!
echo API Docs: http://localhost:!HOST_API_PORT!/docs
echo.
echo 觀看日誌：monitor_backend.bat
echo.
pause
