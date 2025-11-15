@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ════════════════════════════════════════
echo        🔍 系統診斷工具 v2.0
echo ════════════════════════════════════════
echo.

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"
set "BACKEND_DIR=%SERVER_PATH%\backend"
set "LOG_DIR=%BACKEND_DIR%\logs"
set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set REPORT_FILE=diagnostic_report_%TIMESTAMP%.txt

echo 📊 正在生成綜合系統診斷報告...
echo.

:: 開始診斷報告
echo ════════════════════════════════════════ > %REPORT_FILE%
echo       🔍 Form Analysis System 診斷報告 >> %REPORT_FILE%
echo ════════════════════════════════════════ >> %REPORT_FILE%
echo 📅 報告時間: %date% %time% >> %REPORT_FILE%
echo 💻 系統: %OS% >> %REPORT_FILE%
echo 👤 使用者: %USERNAME% >> %REPORT_FILE%
echo 📂 工作目錄: %CD% >> %REPORT_FILE%
echo. >> %REPORT_FILE%

echo [1/12] 系統環境檢查...
:: 系統資訊
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 🖥️  系統資訊 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
systeminfo | findstr /C:"OS Name" /C:"OS Version" /C:"Total Physical Memory" /C:"Available Physical Memory" >> %REPORT_FILE% 2>nul
echo. >> %REPORT_FILE%

echo [2/12] Python 環境檢查...
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 🐍 Python 環境 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
python --version >> %REPORT_FILE% 2>nul
if errorlevel 1 (
    echo ❌ Python 未安裝或未加入 PATH
    echo ❌ Python 未安裝或未加入 PATH >> %REPORT_FILE%
) else (
    echo ✅ Python 已安裝
    echo ✅ Python 已安裝 >> %REPORT_FILE%
    pip --version >> %REPORT_FILE% 2>nul
)
echo. >> %REPORT_FILE%

echo [3/12] Node.js 環境檢查...
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 🟢 Node.js 環境 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
node --version >> %REPORT_FILE% 2>nul
if errorlevel 1 (
    echo ❌ Node.js 未安裝
    echo ❌ Node.js 未安裝 >> %REPORT_FILE%
) else (
    echo ✅ Node.js 已安裝
    echo ✅ Node.js 已安裝 >> %REPORT_FILE%
    npm --version >> %REPORT_FILE% 2>nul
)
echo. >> %REPORT_FILE%

echo [4/12] Docker 環境檢查...
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 🐳 Docker 環境 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
docker --version >> %REPORT_FILE% 2>nul
if errorlevel 1 (
    echo ❌ Docker 未安裝或未啟動
    echo ❌ Docker 未安裝或未啟動 >> %REPORT_FILE%
    set DOCKER_AVAILABLE=false
) else (
    echo ✅ Docker 服務可用
    echo ✅ Docker 服務可用 >> %REPORT_FILE%
    set DOCKER_AVAILABLE=true
    
    docker-compose --version >> %REPORT_FILE% 2>nul
    if errorlevel 1 (
        echo ❌ Docker Compose 未安裝
        echo ❌ Docker Compose 未安裝 >> %REPORT_FILE%
    ) else (
        echo ✅ Docker Compose 可用
        echo ✅ Docker Compose 可用 >> %REPORT_FILE%
    )
    
    docker info >nul 2>nul
    if errorlevel 1 (
        echo ⚠️  Docker 服務未運行
        echo ⚠️  Docker 服務未運行 >> %REPORT_FILE%
    ) else (
        echo ✅ Docker 服務正在運行
        echo ✅ Docker 服務正在運行 >> %REPORT_FILE%
    )
)
echo. >> %REPORT_FILE%

echo [5/12] 專案結構檢查...
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 📁 專案結構 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
set REQUIRED_DIRS=form-analysis-server docs scripts test-data tools
for %%d in (%REQUIRED_DIRS%) do (
    if exist "%%d" (
        echo ✅ %%d\ 目錄存在
        echo ✅ %%d\ 目錄存在 >> %REPORT_FILE%
    ) else (
        echo ❌ %%d\ 目錄不存在
        echo ❌ %%d\ 目錄不存在 >> %REPORT_FILE%
    )
)
echo. >> %REPORT_FILE%

echo [6/12] 連接埠檢查...
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 🌐 連接埠狀態 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
set PORTS=5432 8000 5173 3000
for %%p in (%PORTS%) do (
    netstat -an | findstr ":%%p " >nul 2>nul
    if errorlevel 1 (
        echo ✅ 連接埠 %%p 可用
        echo ✅ 連接埠 %%p 可用 >> %REPORT_FILE%
    ) else (
        echo ⚠️  連接埠 %%p 被占用
        echo ⚠️  連接埠 %%p 被占用 >> %REPORT_FILE%
    )
)
echo. >> %REPORT_FILE%

echo [7/12] 日誌系統檢查...
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 📝 日誌系統 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
if exist "%LOG_DIR%" (
    echo ✅ 日誌目錄存在: %LOG_DIR%
    echo ✅ 日誌目錄存在: %LOG_DIR% >> %REPORT_FILE%
    
    if exist "%LOG_DIR%\app.log" (
        echo ✅ app.log 存在
        echo ✅ app.log 存在 >> %REPORT_FILE%
        for %%i in ("%LOG_DIR%\app.log") do (
            echo    檔案大小: %%~zi bytes >> %REPORT_FILE%
        )
    ) else (
        echo ⚠️  app.log 不存在
        echo ⚠️  app.log 不存在 >> %REPORT_FILE%
    )
    
    if exist "%LOG_DIR%\error.log" (
        echo ✅ error.log 存在
        echo ✅ error.log 存在 >> %REPORT_FILE%
    ) else (
        echo ℹ️  error.log 不存在（正常）
        echo ℹ️  error.log 不存在（正常）>> %REPORT_FILE%
    )
) else (
    echo ⚠️  日誌目錄不存在
    echo ⚠️  日誌目錄不存在 >> %REPORT_FILE%
)
echo. >> %REPORT_FILE%

echo [8/12] 磁碟空間檢查...
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 💾 磁碟空間 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
for /f "skip=1 tokens=1-4" %%a in ('wmic logicaldisk get size^,freespace^,caption 2^>nul') do (
    if not "%%d"=="" (
        set /a total_gb=%%d/1024/1024/1024
        set /a free_gb=%%b/1024/1024/1024
        set /a used_percent=(%%d-%%b)*100/%%d
        echo 磁碟 %%a: 總空間 !total_gb!GB, 可用空間 !free_gb!GB, 使用率 !used_percent!%%
        echo 磁碟 %%a: 總空間 !total_gb!GB, 可用空間 !free_gb!GB, 使用率 !used_percent!%% >> %REPORT_FILE%
    )
)
echo. >> %REPORT_FILE%

echo [9/12] 網路連接檢查...
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 🌍 網路連接 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
ping -n 1 8.8.8.8 >nul 2>nul
if errorlevel 1 (
    echo ❌ 網路連接異常
    echo ❌ 網路連接異常 >> %REPORT_FILE%
) else (
    echo ✅ 網路連接正常
    echo ✅ 網路連接正常 >> %REPORT_FILE%
)
echo. >> %REPORT_FILE%

if "%DOCKER_AVAILABLE%"=="true" (
    echo [10/12] Docker 容器狀態檢查...
    echo ──────────────────────────────────────── >> %REPORT_FILE%
    echo 🐳 Docker 容器狀態 >> %REPORT_FILE%
    echo ──────────────────────────────────────── >> %REPORT_FILE%
    
    cd "%SERVER_PATH%" 2>nul
    if exist "docker-compose.yml" (
        echo ✅ docker-compose.yml 存在
        echo ✅ docker-compose.yml 存在 >> %REPORT_FILE%
        
        docker-compose ps >> %REPORT_FILE% 2>nul
    ) else (
        echo ❌ docker-compose.yml 不存在
        echo ❌ docker-compose.yml 不存在 >> %REPORT_FILE%
    )
    echo. >> %REPORT_FILE%
    
    echo [11/12] Docker 映像檔和資源檢查...
    echo ──────────────────────────────────────── >> %REPORT_FILE%
    echo 🐳 Docker 資源 >> %REPORT_FILE%
    echo ──────────────────────────────────────── >> %REPORT_FILE%
    docker images >> %REPORT_FILE% 2>nul
    echo. >> %REPORT_FILE%
    docker volume ls >> %REPORT_FILE% 2>nul
    echo. >> %REPORT_FILE%
) else (
    echo [10/12] 跳過 Docker 檢查 (Docker 不可用)
    echo [11/12] 跳過 Docker 資源檢查 (Docker 不可用)
)

echo [12/12] 進程檢查...
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 🔄 運行中的相關程序 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
tasklist | findstr /I "python" >> %REPORT_FILE% 2>nul
tasklist | findstr /I "node" >> %REPORT_FILE% 2>nul
tasklist | findstr /I "docker" >> %REPORT_FILE% 2>nul
echo. >> %REPORT_FILE%

:: 建議和總結
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 💡 建議和總結 >> %REPORT_FILE%
echo ──────────────────────────────────────── >> %REPORT_FILE%
echo 1. 如果 Python 或 Node.js 未安裝，請先安裝相應的環境 >> %REPORT_FILE%
echo 2. 確保 Docker 服務正在運行以使用容器化部署 >> %REPORT_FILE%
echo 3. 檢查連接埠占用情況，必要時調整配置或停止衝突服務 >> %REPORT_FILE%
echo 4. 定期監控日誌檔案大小和磁碟空間使用情況 >> %REPORT_FILE%
echo 5. 如有網路問題，檢查防火牆和代理設定 >> %REPORT_FILE%
echo 6. 使用 monitor-logs.bat 監控系統日誌 >> %REPORT_FILE%
echo 7. 使用 log_analyzer.py 進行詳細日誌分析 >> %REPORT_FILE%
echo. >> %REPORT_FILE%

echo ════════════════════════════════════════ >> %REPORT_FILE%
echo 📋 診斷完成時間: %date% %time% >> %REPORT_FILE%
echo ════════════════════════════════════════ >> %REPORT_FILE%

echo ✅ 診斷完成！
echo 📄 報告已保存到: %REPORT_FILE%
echo.
echo � 診斷摘要:
echo ═══════════════════════════════════════════
type %REPORT_FILE% | findstr /C:"✅" /C:"❌" /C:"⚠️ " | more
echo.

echo ════════════════════════════════════════
echo            �🔧 常用修復指令
echo ════════════════════════════════════════
echo 🐳 Docker 相關：
echo    停止所有容器: docker-compose down
echo    清理所有資源: docker-compose down -v --remove-orphans
echo    重建映像檔: docker-compose build --no-cache
echo    檢查磁碟空間: docker system df
echo    清理未使用資源: docker system prune
echo.
echo 📝 日誌相關：
echo    監控日誌: scripts\monitor-logs.bat
echo    分析日誌: python tools\log_analyzer.py
echo    清理日誌: python tools\log_analyzer.py --cleanup
echo.
echo 🚀 服務啟動：
echo    快速啟動: scripts\start-system.bat
echo    Docker 啟動: form-analysis-server\quick-start.bat
echo.

set /p view_report="是否要查看完整診斷報告？(y/N): "
if /i "%view_report%"=="y" (
    echo.
    echo 📄 完整診斷報告:
    echo ═══════════════════════════════════════════
    type %REPORT_FILE%
)

echo.
echo 👋 診斷完成！報告檔案: %REPORT_FILE%
echo 📞 如果問題持續，請提供診斷報告尋求協助
pause