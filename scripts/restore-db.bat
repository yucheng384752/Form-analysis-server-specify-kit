@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================================
:: Database Restore Script (restore-db.bat)
:: ============================================================================
:: 將 .sql 備份檔還原到 Dev 或 Demo 環境的 PostgreSQL。
::
:: Usage:
::   .\restore-db.bat backup.sql           還原到 Dev 環境 (預設)
::   .\restore-db.bat backup.sql --demo    還原到 Demo 環境
:: ============================================================================

set "ENV_MODE=dev"
set "BACKUP_FILE="

:parse_args
if "%~1"=="" goto done_args
if /I "%~1"=="--demo" (
    set "ENV_MODE=demo"
) else (
    if "!BACKUP_FILE!"=="" set "BACKUP_FILE=%~1"
)
shift
goto parse_args
:done_args

if "!BACKUP_FILE!"=="" (
    echo [ERROR] Please specify the backup file.
    echo.
    echo Usage: restore-db.bat ^<backup_file.sql^> [--demo]
    echo.
    echo Examples:
    echo   .\restore-db.bat backups\dev_backup_20260330.sql
    echo   .\restore-db.bat backups\demo_backup.sql --demo
    pause
    exit /b 1
)

if not exist "!BACKUP_FILE!" (
    echo [ERROR] Backup file not found: !BACKUP_FILE!
    pause
    exit /b 1
)

echo.
echo ========================================
echo    Database Restore (%ENV_MODE%)
echo ========================================
echo.

cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

:: Set container and env based on environment
if "%ENV_MODE%"=="demo" (
    set "ENV_FILE=%SERVER_PATH%\.env.demo"
    set "CONTAINER=demo_form_analysis_db"
    set "API_CONTAINER=demo_form_analysis_api"
    set "COMPOSE_PROJECT=form-analysis-demo"
    set "COMPOSE_EXTRA=-f docker-compose.demo.yml --env-file .env.demo"
) else (
    set "ENV_FILE=%SERVER_PATH%\.env.dev"
    set "CONTAINER=form_analysis_db"
    set "API_CONTAINER=form_analysis_api"
    set "COMPOSE_PROJECT=form-analysis-dev"
    set "COMPOSE_EXTRA=--env-file .env.dev"
)

if not exist "%ENV_FILE%" (
    echo [ERROR] Missing %ENV_FILE%
    echo   Please run start-%ENV_MODE%.bat first.
    pause
    exit /b 1
)

:: Read DB credentials
set "PG_USER=app"
set "PG_DB=form_analysis_db"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"POSTGRES_USER=" "%ENV_FILE%"`) do if not "%%b"=="" set "PG_USER=%%b"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"POSTGRES_DB=" "%ENV_FILE%"`) do if not "%%b"=="" set "PG_DB=%%b"

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

:: Check DB container is running
docker ps --format "{{.Names}}" | findstr "!CONTAINER!" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Container !CONTAINER! is not running.
    echo   Please run start-%ENV_MODE%.bat first.
    pause
    exit /b 1
)

for %%f in ("!BACKUP_FILE!") do set "FILE_SIZE=%%~zf"
echo   Backup file: !BACKUP_FILE! (!FILE_SIZE! bytes)
echo   Target:      !CONTAINER! / !PG_DB!
echo.
echo   [WARNING] This will OVERWRITE all data in the %ENV_MODE% database.
echo.
set /p CONFIRM="  Continue? (y/N): "
if /I not "!CONFIRM!"=="y" (
    echo   Cancelled.
    pause
    exit /b 0
)

echo.
echo [1/4] Stopping backend (prevent Alembic conflicts)...
cd /d "%SERVER_PATH%"
%DOCKER_COMPOSE% -p !COMPOSE_PROJECT! !COMPOSE_EXTRA! stop backend >nul 2>&1
echo   Backend stopped.

echo [2/4] Restoring database...
docker exec -i !CONTAINER! psql -U !PG_USER! -d !PG_DB! < "!BACKUP_FILE!" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] psql restore failed.
    echo   Starting backend back up...
    %DOCKER_COMPOSE% -p !COMPOSE_PROJECT! !COMPOSE_EXTRA! start backend >nul 2>&1
    pause
    exit /b 1
)
echo   Database restored.

echo [3/4] Restarting backend (runs Alembic upgrade if needed)...
%DOCKER_COMPOSE% -p !COMPOSE_PROJECT! !COMPOSE_EXTRA! start backend >nul 2>&1

:: Wait for backend health
set "BACKEND_OK=0"
for /L %%i in (1,1,12) do (
    if "!BACKEND_OK!"=="0" (
        timeout /t 5 /nobreak >nul
        set "PORT=18002"
        if "%ENV_MODE%"=="demo" set "PORT=18102"
        curl -4 -sf http://127.0.0.1:!PORT!/healthz >nul 2>&1
        if not errorlevel 1 set "BACKEND_OK=1"
    )
)

echo [4/4] Verifying...
if "!BACKEND_OK!"=="1" (
    echo   Backend healthz: OK
) else (
    echo   Backend healthz: not ready (check logs: docker logs !API_CONTAINER!)
)

:: Quick row count check
echo.
echo   Table row counts:
docker exec !CONTAINER! psql -U !PG_USER! -d !PG_DB! -t -c "SELECT 'tenants: ' || COUNT(*) FROM tenants UNION ALL SELECT 'tenant_users: ' || COUNT(*) FROM tenant_users UNION ALL SELECT 'p1_records: ' || COUNT(*) FROM p1_records UNION ALL SELECT 'p2_records: ' || COUNT(*) FROM p2_records UNION ALL SELECT 'p3_records: ' || COUNT(*) FROM p3_records ORDER BY 1;" 2>nul

echo.
echo ========================================
echo   Restore complete!
echo ========================================
echo.
echo   Frontend: http://127.0.0.1:!PORT:-18002!
echo   Use the same login credentials as the old machine.
echo.
pause
