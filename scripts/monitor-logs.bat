@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ════════════════════════════════════════
echo           日誌監控工具
echo ════════════════════════════════════════
echo.

set LOG_DIR=form-analysis-server\backend\logs
set APP_LOG=%LOG_DIR%\app.log
set ERROR_LOG=%LOG_DIR%\error.log

:: 檢查日誌目錄是否存在
if not exist "%LOG_DIR%" (
    echo  日誌目錄不存在: %LOG_DIR%
    echo    請先啟動系統以建立日誌檔案
    pause
    exit /b 1
)

:MENU
cls
echo ════════════════════════════════════════
echo           日誌監控工具
echo ════════════════════════════════════════
echo.
echo  可用選項：
echo    [1]  查看應用程式日誌 (最新50行)
echo    [2]  查看錯誤日誌 (最新50行) 
echo    [3] 即時監控日誌
echo    [4]  統計資訊
echo    [5]  搜尋日誌
echo    [6]  清理舊日誌
echo    [0]  退出
echo.

set /p choice="請選擇操作 (0-6): "

if "%choice%"=="1" goto VIEW_APP_LOG
if "%choice%"=="2" goto VIEW_ERROR_LOG
if "%choice%"=="3" goto MONITOR_LOG
if "%choice%"=="4" goto SHOW_STATS
if "%choice%"=="5" goto SEARCH_LOG
if "%choice%"=="6" goto CLEANUP_LOG
if "%choice%"=="0" goto EXIT
goto MENU

:VIEW_APP_LOG
cls
echo  應用程式日誌 (最新50行):
echo ════════════════════════════════════════
if exist "%APP_LOG%" (
    powershell -Command "Get-Content '%APP_LOG%' -Tail 50 | ForEach-Object { $_ }"
) else (
    echo   日誌檔案不存在: %APP_LOG%
)
echo.
pause
goto MENU

:VIEW_ERROR_LOG
cls
echo  錯誤日誌 (最新50行):
echo ════════════════════════════════════════
if exist "%ERROR_LOG%" (
    powershell -Command "Get-Content '%ERROR_LOG%' -Tail 50 | ForEach-Object { $_ }"
) else (
    echo  沒有錯誤日誌檔案
)
echo.
pause
goto MENU

:MONITOR_LOG
cls
echo 即時監控日誌 (Ctrl+C 停止):
echo ════════════════════════════════════════
if exist "%APP_LOG%" (
    powershell -Command "Get-Content '%APP_LOG%' -Wait -Tail 10"
) else (
    echo   日誌檔案不存在: %APP_LOG%
    pause
)
goto MENU

:SHOW_STATS
cls
echo  日誌統計資訊:
echo ════════════════════════════════════════

if exist "%APP_LOG%" (
    echo 應用程式日誌統計:
    for /f %%i in ('powershell -Command "(Get-Content '%APP_LOG%' | Measure-Object -Line).Lines"') do (
        echo    總行數: %%i
    )
    
    for /f %%i in ('powershell -Command "(Get-Content '%APP_LOG%' | Select-String 'info' | Measure-Object).Count"') do (
        echo    INFO: %%i
    )
    
    for /f %%i in ('powershell -Command "(Get-Content '%APP_LOG%' | Select-String 'warning' | Measure-Object).Count"') do (
        echo    WARNING: %%i
    )
    
    for /f %%i in ('powershell -Command "(Get-Content '%APP_LOG%' | Select-String 'error' | Measure-Object).Count"') do (
        echo    ERROR: %%i
    )
    
    echo.
    echo  最近活動:
    for /f %%i in ('powershell -Command "(Get-Content '%APP_LOG%' | Select-String '檔案上傳開始' | Measure-Object).Count"') do (
        echo    檔案上傳: %%i 次
    )
    
    for /f %%i in ('powershell -Command "(Get-Content '%APP_LOG%' | Select-String '查詢完成' | Measure-Object).Count"') do (
        echo    資料查詢: %%i 次
    )
) else (
    echo   日誌檔案不存在
)

echo.
echo 💾 檔案大小:
if exist "%APP_LOG%" (
    for %%i in ("%APP_LOG%") do echo    app.log: %%~zi bytes
)
if exist "%ERROR_LOG%" (
    for %%i in ("%ERROR_LOG%") do echo    error.log: %%~zi bytes
)

echo.
pause
goto MENU

:SEARCH_LOG
cls
echo  搜尋日誌:
echo ════════════════════════════════════════
set /p search_term="請輸入搜尋關鍵字: "

if "%search_term%"=="" goto MENU

echo.
echo 搜尋結果 (包含 "%search_term%"):
echo ────────────────────────────────────────
if exist "%APP_LOG%" (
    powershell -Command "Get-Content '%APP_LOG%' | Select-String '%search_term%' | Select-Object -First 20"
) else (
    echo   日誌檔案不存在
)

echo.
pause
goto MENU

:CLEANUP_LOG
cls
echo  清理舊日誌:
echo ════════════════════════════════════════
echo   這將刪除所有 .log.* 備份檔案
echo.
set /p confirm="確定要清理嗎？(y/N): "

if /i "%confirm%"=="y" (
    echo.
    echo 正在清理...
    if exist "%LOG_DIR%\*.log.*" (
        del /q "%LOG_DIR%\*.log.*"
        echo  清理完成
    ) else (
        echo   沒有備份檔案需要清理
    )
) else (
    echo 已取消
)

echo.
pause
goto MENU

:EXIT
echo.
echo 👋 再見！
exit /b 0