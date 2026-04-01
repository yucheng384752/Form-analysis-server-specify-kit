@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================================
:: Database Backup Script (backup-db.bat)
:: ============================================================================
:: 將 Dev 或 Demo 環境的 PostgreSQL 資料庫匯出為 .sql 備份檔。
::
:: Usage:
::   .\backup-db.bat              備份 Dev 環境 (預設)
::   .\backup-db.bat --demo       備份 Demo 環境
::   .\backup-db.bat --output C:\path\to\backup.sql  指定輸出路徑
:: ============================================================================

set "ENV_MODE=dev"
set "OUTPUT_PATH="

:parse_args
if "%~1"=="" goto done_args
if /I "%~1"=="--demo" set "ENV_MODE=demo"
if /I "%~1"=="--output" (
    set "OUTPUT_PATH=%~2"
    shift
)
shift
goto parse_args
:done_args

echo.
echo ========================================
echo    Database Backup (%ENV_MODE%)
echo ========================================
echo.

cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"
set "BACKUP_DIR=%PROJECT_ROOT%\backups"

:: Set container and DB names based on environment
if "%ENV_MODE%"=="demo" (
    set "ENV_FILE=%SERVER_PATH%\.env.demo"
    set "CONTAINER=demo_form_analysis_db"
) else (
    set "ENV_FILE=%SERVER_PATH%\.env.dev"
    set "CONTAINER=form_analysis_db"
)

if not exist "%ENV_FILE%" (
    echo [ERROR] Missing %ENV_FILE%
    echo   Please run start-%ENV_MODE%.bat first to create the environment.
    pause
    exit /b 1
)

:: Read DB credentials from env file
set "PG_USER=app"
set "PG_DB=form_analysis_db"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"POSTGRES_USER=" "%ENV_FILE%"`) do if not "%%b"=="" set "PG_USER=%%b"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"POSTGRES_DB=" "%ENV_FILE%"`) do if not "%%b"=="" set "PG_DB=%%b"

:: Check container is running
docker ps --format "{{.Names}}" | findstr "!CONTAINER!" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Container !CONTAINER! is not running.
    echo   Please start the %ENV_MODE% environment first.
    pause
    exit /b 1
)

:: Generate output path if not specified
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

if "!OUTPUT_PATH!"=="" (
    set "TS=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%"
    set "TS=!TS: =0!"
    set "OUTPUT_PATH=%BACKUP_DIR%\%ENV_MODE%_backup_!TS!.sql"
)

echo [1/2] Exporting database...
echo   Container: !CONTAINER!
echo   Database:  !PG_DB!
echo   User:      !PG_USER!
echo.

docker exec !CONTAINER! pg_dump -U !PG_USER! -d !PG_DB! --clean --if-exists --no-owner --no-privileges > "!OUTPUT_PATH!" 2>&1
if errorlevel 1 (
    echo [ERROR] pg_dump failed. Check container logs:
    echo   docker logs !CONTAINER!
    pause
    exit /b 1
)

:: Verify the backup file has content
for %%f in ("!OUTPUT_PATH!") do set "FILE_SIZE=%%~zf"
if "!FILE_SIZE!"=="0" (
    echo [ERROR] Backup file is empty. Database may not have data.
    del "!OUTPUT_PATH!" >nul 2>&1
    pause
    exit /b 1
)

echo [2/2] Backup complete!
echo.
echo ========================================
echo   Backup saved to:
echo   !OUTPUT_PATH!
echo   Size: !FILE_SIZE! bytes
echo ========================================
echo.
echo Next steps (on new machine):
echo   1. Copy this repo folder + backup file to the new machine
echo   2. Install Docker Desktop
echo   3. Run: scripts\start-dev.bat
echo   4. Run: scripts\restore-db.bat "!OUTPUT_PATH!"
echo.
pause
