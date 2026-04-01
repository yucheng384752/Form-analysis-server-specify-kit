@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo.
echo ========================================
echo     Form Analysis - Stop All
echo ========================================
echo.

cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

:: Detect Docker Compose
set "DOCKER_COMPOSE=docker-compose"
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Docker Compose is not available.
        pause
        exit /b 1
    ) else (
        set "DOCKER_COMPOSE=docker compose"
    )
)

cd /d "%SERVER_PATH%"

echo [1/3] Stopping dev environment (form-analysis-dev)...
%DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev down --remove-orphans 2>nul
if not errorlevel 1 (
    echo   Dev services stopped.
) else (
    echo   Dev environment was not running or already stopped.
)

echo.
echo [2/3] Stopping demo environment (form-analysis-demo)...
%DOCKER_COMPOSE% -p form-analysis-demo -f docker-compose.demo.yml --env-file .env.demo down --remove-orphans 2>nul
if not errorlevel 1 (
    echo   Demo services stopped.
) else (
    echo   Demo environment was not running or already stopped.
)

echo.
echo [3/3] Cleaning up monitor scripts...
if exist "%PROJECT_ROOT%\scripts\monitor_backend.bat" del "%PROJECT_ROOT%\scripts\monitor_backend.bat" 2>nul
if exist "%PROJECT_ROOT%\scripts\monitor_frontend.bat" del "%PROJECT_ROOT%\scripts\monitor_frontend.bat" 2>nul

echo.
echo ========================================
echo            All services stopped
echo ========================================
echo.
echo   Restart dev:  scripts\start-dev.bat
echo   Restart demo: scripts\start-demo.bat
echo.
pause
