@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================================
:: Development Environment Startup Script (start-dev.bat)
:: ============================================================================
:: 使用 docker-compose.yml (development target) + .env.dev
:: 源碼掛載，支援 hot reload
:: Ports: 180xx (18001=DB, 18002=API, 18003=Frontend)
:: ============================================================================

set "PAUSE_ON_EXIT=1"
if /I "%~1"=="--no-pause" set "PAUSE_ON_EXIT=0"
if /I "%CI%"=="true" set "PAUSE_ON_EXIT=0"
if /I "%CI%"=="1" set "PAUSE_ON_EXIT=0"
if /I "%GITHUB_ACTIONS%"=="true" set "PAUSE_ON_EXIT=0"

echo.
echo ========================================
echo    Development Startup (env.dev)
echo ========================================
echo.

cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"
set "ENV_FILE=%SERVER_PATH%\.env.dev"
set "COMPOSE_FILE=%SERVER_PATH%\docker-compose.yml"

if not exist "%ENV_FILE%" (
    echo [ERROR] Missing %ENV_FILE%
    echo Please create it first. Copy .env.example to .env.dev and fill required values.
    call :maybe_pause
    exit /b 1
)

if not exist "%COMPOSE_FILE%" (
    echo [ERROR] Missing %COMPOSE_FILE%
    call :maybe_pause
    exit /b 1
)

set "DOCKER_COMPOSE=docker-compose"
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Docker Compose is not available.
        call :maybe_pause
        exit /b 1
    ) else (
        set "DOCKER_COMPOSE=docker compose"
    )
)

:: Read ports from env file
set "HOST_API_PORT=18002"
set "HOST_FRONTEND_PORT=18003"
set "HOST_DB_PORT=18001"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"HOST_API_PORT=" "%ENV_FILE%"`) do if not "%%b"=="" set "HOST_API_PORT=%%b"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"FRONTEND_PORT=" "%ENV_FILE%"`) do if not "%%b"=="" set "HOST_FRONTEND_PORT=%%b"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"POSTGRES_PORT=" "%ENV_FILE%"`) do if not "%%b"=="" set "HOST_DB_PORT=%%b"

echo [1/4] Stopping existing dev containers...
cd /d "%SERVER_PATH%"
%DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev down --remove-orphans

echo.
echo [2/4] Starting development stack (with hot reload)...
%DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev up -d --build
if errorlevel 1 (
    echo [ERROR] Dev stack failed to start.
    %DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev logs --tail=80
    call :maybe_pause
    exit /b 1
)

echo.
echo [3/4] Service status
%DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev ps

echo.
echo [4/4] Quick health checks
timeout /t 5 /nobreak >nul
curl -4 -s http://127.0.0.1:!HOST_API_PORT!/healthz >nul 2>&1
if errorlevel 1 (
    echo - Backend healthz: not ready yet (may take a moment)
) else (
    echo - Backend healthz: OK
)

curl -4 -s http://127.0.0.1:!HOST_FRONTEND_PORT! >nul 2>&1
if errorlevel 1 (
    echo - Frontend: not ready yet (may take a moment)
) else (
    echo - Frontend: OK
)

if "!PAUSE_ON_EXIT!"=="1" (
    echo.
    echo ========================================
    echo   Development Environment Ready
    echo ========================================
    echo.
    echo Development links:
    echo - Frontend: http://localhost:!HOST_FRONTEND_PORT!
    echo - Backend API: http://localhost:!HOST_API_PORT!
    echo - API Docs: http://localhost:!HOST_API_PORT!/docs
    echo - PostgreSQL: localhost:!HOST_DB_PORT!
    echo.
    echo Source code is mounted - changes will hot reload.
    echo.
    echo Press any key to exit...
)

call :maybe_pause
exit /b 0

:maybe_pause
if "!PAUSE_ON_EXIT!"=="1" pause >nul
exit /b 0
