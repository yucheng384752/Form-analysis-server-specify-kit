@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================================
:: Build Demo Images Script (build-demo-images.bat)
:: ============================================================================
:: 建立穩定的 Demo 環境 Docker images
:: - form-analysis-backend:demo
:: - form-analysis-frontend:demo
:: 使用 production target，代碼打包進 image
:: ============================================================================

set "PAUSE_ON_EXIT=1"
if /I "%~1"=="--no-pause" set "PAUSE_ON_EXIT=0"
if /I "%CI%"=="true" set "PAUSE_ON_EXIT=0"

echo.
echo ========================================
echo   Building Demo Images (Production)
echo ========================================
echo.

cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"
set "COMPOSE_FILE=%SERVER_PATH%\docker-compose.demo.yml"
set "ENV_FILE=%SERVER_PATH%\.env.demo"

if not exist "%COMPOSE_FILE%" (
    echo [ERROR] Missing %COMPOSE_FILE%
    call :maybe_pause
    exit /b 1
)

if not exist "%ENV_FILE%" (
    echo [ERROR] Missing %ENV_FILE%
    echo Please create it first.
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

cd /d "%SERVER_PATH%"

echo [1/3] Building backend image (form-analysis-backend:demo)...
%DOCKER_COMPOSE% -p form-analysis-demo -f docker-compose.demo.yml --env-file .env.demo build backend
if errorlevel 1 (
    echo [ERROR] Failed to build backend image.
    call :maybe_pause
    exit /b 1
)
echo - Backend image built successfully.

echo.
echo [2/3] Building frontend image (form-analysis-frontend:demo)...
%DOCKER_COMPOSE% -p form-analysis-demo -f docker-compose.demo.yml --env-file .env.demo build frontend
if errorlevel 1 (
    echo [ERROR] Failed to build frontend image.
    call :maybe_pause
    exit /b 1
)
echo - Frontend image built successfully.

echo.
echo [3/3] Verifying images...
docker images | findstr "form-analysis"
if errorlevel 1 (
    echo [WARNING] Could not list images.
)

echo.
echo ========================================
echo   Demo Images Built Successfully
echo ========================================
echo.
echo Images created:
echo - form-analysis-backend:demo
echo - form-analysis-frontend:demo
echo.
echo These images contain the current code baked in.
echo To start demo environment, run: start-demo.bat
echo.
echo Note: To update demo environment with new code,
echo run this script again to rebuild images.
echo.

call :maybe_pause
exit /b 0

:maybe_pause
if "!PAUSE_ON_EXIT!"=="1" pause >nul
exit /b 0
