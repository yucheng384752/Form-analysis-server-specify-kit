@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
echo.
echo ========================================
echo     表單分析系統 - 啟動腳本
echo ========================================
echo.

REM 設置工作目錄
@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

REM --------------------------------------------------------
REM 環境檔（.env）初始化：讓 docker-compose 變數可正確帶入
REM --------------------------------------------------------
if not exist "%SERVER_PATH%\.env" (
    if exist "%SERVER_PATH%\.env.example" (
        echo [0/6] 偵測到未設定環境檔，建立 %SERVER_PATH%\.env ...
        copy "%SERVER_PATH%\.env.example" "%SERVER_PATH%\.env" >nul
    ) else (
        echo [0/6] 找不到 %SERVER_PATH%\.env 與 .env.example，將直接使用系統環境變數
    )
)

REM 產生 ADMIN_API_KEYS（僅用於本機 demo bootstrap：建立 tenant / 建立 tenant user）
REM 若已存在 ADMIN_API_KEYS=（非註解），則不覆蓋。
if exist "%SERVER_PATH%\.env" (
    findstr /R /B /C:"ADMIN_API_KEYS=" "%SERVER_PATH%\.env" >nul 2>&1
    if errorlevel 1 (
        for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')"`) do set "GENERATED_ADMIN_KEY=%%i"
        echo.>> "%SERVER_PATH%\.env"
        echo ADMIN_API_KEYS=!GENERATED_ADMIN_KEY!>> "%SERVER_PATH%\.env"
        echo [0/6] 已自動產生 ADMIN_API_KEYS（Header: X-Admin-API-Key）:
        echo   !GENERATED_ADMIN_KEY!
        echo   你可以把它貼到前端 Register Page 的 Admin Key 欄位使用。
    )
)

REM 顯示 API base URL（docker-compose 會把主機的 API_PORT 對應到容器 8000）
set "HOST_API_PORT=18002"
if exist "%SERVER_PATH%\.env" (
    for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"API_PORT=" "%SERVER_PATH%\.env"`) do (
        if not "%%b"=="" set "HOST_API_PORT=%%b"
    )
)
echo [0/6] API base URL: http://localhost:!HOST_API_PORT!
echo [0/6] PowerShell 提示：請用 curl.exe 或 Invoke-RestMethod 傳 headers
echo   curl.exe -H "X-Admin-API-Key: <key>" http://localhost:!HOST_API_PORT!/api/auth/whoami
echo   Invoke-RestMethod http://localhost:!HOST_API_PORT!/api/auth/whoami -Headers @{"X-Admin-API-Key"="<key>"}

REM --------------------------------------------------------
REM PDFtoCSV server 連線檢查（外部服務，可選）
REM - 若未設定 PDF_SERVER_URL，則跳過
REM - 設定 SKIP_PDF_SERVER_CHECK=1 可略過檢查
REM - 設定 PDF_SERVER_CHECK_STRICT=1 則失敗直接中止（不詢問）
REM --------------------------------------------------------
if /I "%SKIP_PDF_SERVER_CHECK%"=="1" (
    echo [0/6] 已略過 PDFtoCSV server 連線檢查（SKIP_PDF_SERVER_CHECK=1）
) else (
    set "PDF_SERVER_URL_FROM_ENVFILE="
    if exist "%SERVER_PATH%\.env" (
        for /f "usebackq tokens=1* delims==" %%a in (`findstr /R /B /C:"PDF_SERVER_URL=" "%SERVER_PATH%\.env"`) do (
            set "PDF_SERVER_URL_FROM_ENVFILE=%%b"
        )
    )

    set "PDF_SERVER_URL_EFFECTIVE=%PDF_SERVER_URL%"
    if "!PDF_SERVER_URL_EFFECTIVE!"=="" set "PDF_SERVER_URL_EFFECTIVE=!PDF_SERVER_URL_FROM_ENVFILE!"
    set "PDF_SERVER_URL_EFFECTIVE=!PDF_SERVER_URL_EFFECTIVE:"=!"

    if "!PDF_SERVER_URL_EFFECTIVE!"=="" (
        echo [0/6] 未設定 PDF_SERVER_URL，略過 PDFtoCSV server 連線檢查
    ) else (
        echo [0/6] 檢查 PDFtoCSV server 連線：!PDF_SERVER_URL_EFFECTIVE!
        powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $base=$env:PDF_SERVER_URL_EFFECTIVE; if([string]::IsNullOrWhiteSpace($base)){ exit 0 }; $base=$base.Trim(); $paths=@('/healthz','/health','/'); foreach($p in $paths){ try { $u=$base.TrimEnd('/') + $p; $r=Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 3 -Method GET; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 500){ exit 0 } } catch { } }; try { $uri=[Uri]$base; $port=$uri.Port; if($port -le 0){ $port = if($uri.Scheme -eq 'https'){443}else{80} }; $tcp=Test-NetConnection -ComputerName $uri.Host -Port $port -WarningAction SilentlyContinue; if($tcp.TcpTestSucceeded){ exit 0 } } catch { }; exit 1" >nul 2>&1
        if errorlevel 1 (
            echo  [WARN] 無法連線到 PDFtoCSV server（將影響 PDF 轉檔功能）
            echo   - 建議確認 PDF_SERVER_URL 是否正確、服務是否已啟動
            echo   - 若要略過此檢查：設定 SKIP_PDF_SERVER_CHECK=1
            if /I "%PDF_SERVER_CHECK_STRICT%"=="1" (
                echo  [ERROR] PDF_SERVER_CHECK_STRICT=1：中止啟動
                pause
                exit /b 1
            )
            choice /M "PDFtoCSV server 目前不可用，仍要繼續啟動嗎"
            if errorlevel 2 (
                echo  使用者選擇中止
                exit /b 1
            )
            echo  使用者選擇繼續（PDF 轉檔可能失敗）
        ) else (
            echo  PDFtoCSV server 連線檢查通過
        )
    )
)

REM 檢查 Docker 是否執行
echo [1/6] 檢查 Docker 服務狀態...
docker --version >nul 2>&1
if errorlevel 1 (
    echo  Docker 未安裝或未啟動
    echo    請安裝 Docker Desktop 並確保服務正在執行
    pause
    exit /b 1
) else (
    echo  Docker 服務正常
)

REM 檢查 Docker Compose 是否可用
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo  Docker Compose 未安裝或不可用
    echo    請確保 Docker Compose 已正確安裝
    pause
    exit /b 1
) else (
    echo  Docker Compose 可用
)

REM 檢查 docker-compose 檔案
echo  檢查路徑: %SERVER_PATH%\docker-compose.yml
if not exist "%SERVER_PATH%\docker-compose.yml" (
    echo  找不到 docker-compose.yml 檔案
    echo    路徑: %SERVER_PATH%\docker-compose.yml
    echo    項目根目錄: %PROJECT_ROOT%
    echo    服務器路徑: %SERVER_PATH%
    echo    請確認您在專案根目錄執行此腳本
    pause
    exit /b 1
) else (
    echo  找到 docker-compose.yml 檔案
)

REM 預先診斷常見問題
echo.
echo  預先診斷檢查...

REM 檢查端口佔用並自動處理
set "port_conflict=false"
netstat -an | find ":5432" | find "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   檢測到端口 5432 PostgreSQL 被佔用
    echo     檢查是否為其他 Docker 容器...
    for /f "tokens=*" %%i in ('docker ps --filter "publish=5432" --format "{{.Names}}"') do (
        echo     停止容器: %%i
        docker stop %%i >nul 2>&1
    )
    set "port_conflict=true"
)

netstat -an | find ":8000" | find "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   檢測到端口 8000 API 被佔用
    echo     檢查是否為其他 Docker 容器...
    for /f "tokens=*" %%i in ('docker ps --filter "publish=8000" --format "{{.Names}}"') do (
        echo     停止容器: %%i
        docker stop %%i >nul 2>&1
    )
    set "port_conflict=true"
)

netstat -an | find ":3000" | find "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   檢測到端口 3000 被佔用
    echo     檢查是否為其他 Docker 容器...
    for /f "tokens=*" %%i in ('docker ps --filter "publish=3000" --format "{{.Names}}"') do (
        echo     停止容器: %%i
        docker stop %%i >nul 2>&1
    )
    set "port_conflict=true"
)

netstat -an | find ":5173" | find "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   檢測到端口 5173 前端被佔用
    echo     檢查是否為其他 Docker 容器...
    for /f "tokens=*" %%i in ('docker ps --filter "publish=5173" --format "{{.Names}}"') do (
        echo     停止容器: %%i
        docker stop %%i >nul 2>&1
    )
    set "port_conflict=true"
)

if "!port_conflict!"=="true" (
    echo     執行額外清理以釋放端口...
    docker-compose -f "%SERVER_PATH%\docker-compose.yml" down --remove-orphans >nul 2>&1
    timeout /t 2 /nobreak >nul
)

REM 檢查 Docker 資源
echo     端口檢查完成

REM 檢查是否有殘留容器
docker ps -a --format "table {{.Names}}" | find "form_analysis" >nul 2>&1
if not errorlevel 1 (
    echo     發現現有容器，將在下一步清理
) else (
    echo     無殘留容器
)

REM 檢查是否為首次啟動
set "FIRST_TIME_SETUP=false"
docker volume ls | find "form-analysis-server_postgres_data" >nul 2>&1
if errorlevel 1 (
    echo     檢測到首次啟動，將執行完整初始化
    set "FIRST_TIME_SETUP=true"
) else (
    echo     檢測到現有資料，將執行正常啟動
)

echo.
echo [2/6] 停止現有容器並清理...
cd "%SERVER_PATH%"

if "!FIRST_TIME_SETUP!"=="true" (
    echo     首次啟動：保留資料卷，清理容器
    docker-compose down --remove-orphans
) else (
    echo     正常啟動：清理現有容器
    docker-compose down --remove-orphans
)

if errorlevel 1 (
    echo   清理容器時遇到問題，繼續執行...
)

echo.
echo [3/6] 啟動 PostgreSQL 資料庫...
docker-compose up -d db
if errorlevel 1 (
    echo  資料庫啟動失敗
    pause
    exit /b 1
)

echo     等待資料庫健康檢查...
set /a counter=0
:db_check
set /a counter+=1

REM 檢查容器狀態
docker-compose ps db --format "table {{.State}}" | find "running" >nul 2>&1
if errorlevel 1 (
    echo  資料庫容器未執行，檢查啟動日誌：
    docker-compose logs --tail=20 db
    pause
    exit /b 1
)

REM 檢查健康狀態
docker-compose ps db --format "table {{.Status}}" | find "healthy" >nul 2>&1
if not errorlevel 1 (
    echo  資料庫已就緒（健康檢查通過）
    
    if "!FIRST_TIME_SETUP!"=="true" (
        echo.
        echo     首次啟動：檢查資料庫初始化...
        timeout /t 3 /nobreak > nul
        docker-compose logs db | find "Database initialized successfully" >nul 2>&1
        if not errorlevel 1 (
            echo     資料庫初始化腳本執行成功
        ) else (
            echo      資料庫基礎結構已建立
        )
    )
    
    goto db_ready
)

REM 如果還在啟動期間，檢查是否有 "starting" 狀態
docker-compose ps db --format "table {{.Status}}" | find "starting" >nul 2>&1
if not errorlevel 1 (
    echo     資料庫健康檢查啟動中... (%counter%/60)
) else (
    REM 檢查是否有 "unhealthy" 狀態
    docker-compose ps db --format "table {{.Status}}" | find "unhealthy" >nul 2>&1
    if not errorlevel 1 (
        echo  資料庫健康檢查失敗，查看日誌：
        docker-compose logs --tail=30 db
        echo.
        echo  常見解決方案：
        echo    1. 檢查 PostgreSQL 密碼設定
        echo    2. 清理舊的資料卷：docker-compose down -v
        echo    3. 檢查端口 5432 是否被佔用
        pause
        exit /b 1
    ) else (
        echo     等待資料庫啟動... (%counter%/60)
    )
)

if %counter% geq 60 (
    echo  資料庫啟動超時（等待 120 秒），詳細診斷：
    echo.
    echo  容器狀態：
    docker-compose ps db
    echo.
    echo  最近日誌：
    docker-compose logs --tail=50 db
    echo.
    echo  建議排除步驟：
    echo    1. 檢查 Docker 資源是否足夠
    echo    2. 重新啟動 Docker Desktop
    echo    3. 清理資料卷：docker-compose down -v
    echo    4. 檢查防火牆設定
    pause
    exit /b 1
)

timeout /t 2 /nobreak > nul
goto db_check
:db_ready

echo.
echo [4/6] 啟動後端 API 服務...
docker-compose up -d --build backend
if errorlevel 1 (
    echo  後端服務啟動失敗
    pause
    exit /b 1
)

if "!FIRST_TIME_SETUP!"=="true" (
    echo     首次啟動：後端將自動執行資料庫遷移...
)

echo     等待後端服務健康檢查...
set /a counter=0
:backend_check
set /a counter+=1

REM 檢查容器執行狀態
docker-compose ps backend --format "table {{.State}}" | find "running" >nul 2>&1
if errorlevel 1 (
    echo  後端容器未執行，檢查建置和啟動日誌：
    docker-compose logs --tail=30 backend
    pause
    exit /b 1
)

REM 檢查健康狀態
docker-compose ps backend --format "table {{.Status}}" | find "healthy" >nul 2>&1
if not errorlevel 1 (
    echo  後端服務已就緒（健康檢查通過）
    
    if "!FIRST_TIME_SETUP!"=="true" (
        echo.
        echo     檢查資料庫遷移執行狀態...
        timeout /t 2 /nobreak > nul
        docker-compose logs backend | find "Database migrations completed successfully" >nul 2>&1
        if not errorlevel 1 (
            echo     資料庫遷移執行成功
        ) else (
            docker-compose logs backend | find "Database initialized successfully" >nul 2>&1
            if not errorlevel 1 (
                echo     資料庫初始化完成
            ) else (
                echo      後端服務正常啟動
            )
        )
    )
    
    goto backend_ready
)

REM 檢查是否在啟動期間
docker-compose ps backend --format "table {{.Status}}" | find "starting\|health:" >nul 2>&1
if not errorlevel 1 (
    echo     後端服務啟動中，等待健康檢查... (%counter%/45)
) else (
    echo     等待後端服務完成啟動... (%counter%/45)
)

if %counter% geq 45 (
    echo  後端服務啟動超時（等待 90 秒），診斷資訊：
    echo.
    echo  容器狀態：
    docker-compose ps backend
    echo.
    echo  最近日誌：
    docker-compose logs --tail=50 backend
    echo.
    echo  常見問題檢查：
    echo    1. 資料庫連線是否正常
    echo    2. Python 依賴是否正確安裝  
    echo    3. 端口 8000 是否被佔用
    echo    4. 環境變數設定是否正確
    pause
    exit /b 1
)

timeout /t 2 /nobreak > nul
goto backend_check
:backend_ready

echo.
echo [5/6] 啟動前端應用...
docker-compose up -d --build frontend
if errorlevel 1 (
    echo  前端服務啟動失敗，嘗試以 --no-cache 重新建置（可能是 Docker BuildKit 快取損壞）...
    docker-compose build --no-cache frontend
    if errorlevel 1 (
        echo  前端服務建置仍然失敗
        echo.
        echo  建議排除步驟：
        echo    1. 重新啟動 Docker Desktop
        echo    2. 清理 build cache：docker builder prune -af
        echo    3. 重新執行本腳本
        pause
        exit /b 1
    )
    docker-compose up -d frontend
    if errorlevel 1 (
        echo  前端服務啟動仍然失敗
        pause
        exit /b 1
    )
)

echo     檢查前端依賴（node_modules）是否包含 recharts...
docker exec form_analysis_frontend sh -lc "test -d node_modules/recharts || npm ci --silent" >nul 2>&1

REM 重新啟動前端，確保新安裝的依賴生效
docker-compose restart frontend >nul 2>&1

echo     等待前端服務健康檢查...
set /a counter=0
:frontend_check
set /a counter+=1

REM 檢查容器執行狀態
docker-compose ps frontend --format "table {{.State}}" | find "running" >nul 2>&1
if errorlevel 1 (
    echo  前端容器未執行，檢查建置和啟動日誌：
    docker-compose logs --tail=30 frontend
    pause
    exit /b 1
)

REM 檢查健康狀態
docker-compose ps frontend --format "table {{.Status}}" | find "healthy" >nul 2>&1
if not errorlevel 1 (
    echo  前端服務已就緒（健康檢查通過）
    goto frontend_ready
)

REM 檢查是否在啟動期間
docker-compose ps frontend --format "table {{.Status}}" | find "starting\|health:" >nul 2>&1
if not errorlevel 1 (
    echo     前端服務啟動中，等待健康檢查... (%counter%/40)
) else (
    echo     等待前端服務完成啟動... (%counter%/40)
)

if %counter% geq 40 (
    echo  前端服務啟動超時（等待 80 秒），診斷資訊：
    echo.
    echo  容器狀態：
    docker-compose ps frontend
    echo.
    echo  最近日誌：
    docker-compose logs --tail=50 frontend
    echo.
    echo  常見問題檢查：
    echo    1. Node.js 依賴是否正確安裝
    echo    2. Vite 開發伺服器配置  
    echo    3. 端口 5173 是否被佔用
    echo    4. 後端 API 連線是否正常
    pause
    exit /b 1
)

timeout /t 2 /nobreak > nul
goto frontend_check
:frontend_ready

echo.
echo [6/6] 啟動監控終端機...

REM 建立後端日誌監控腳本
echo @echo off > "%PROJECT_ROOT%\monitor_backend.bat"
echo chcp 65001 ^> nul >> "%PROJECT_ROOT%\monitor_backend.bat"
echo title 表單分析系統 - 後端日誌監控 >> "%PROJECT_ROOT%\monitor_backend.bat"
echo cd /d "%SERVER_PATH%" >> "%PROJECT_ROOT%\monitor_backend.bat"
echo echo ======================================== >> "%PROJECT_ROOT%\monitor_backend.bat"
echo echo     後端 API 服務日誌監控 >> "%PROJECT_ROOT%\monitor_backend.bat"
echo echo ======================================== >> "%PROJECT_ROOT%\monitor_backend.bat"
echo echo 後端服務 URL: http://localhost:18002 >> "%PROJECT_ROOT%\monitor_backend.bat"
echo echo API 文檔: http://localhost:18002/docs >> "%PROJECT_ROOT%\monitor_backend.bat"
echo echo ======================================== >> "%PROJECT_ROOT%\monitor_backend.bat"
echo echo. >> "%PROJECT_ROOT%\monitor_backend.bat"
echo docker-compose logs -f backend db >> "%PROJECT_ROOT%\monitor_backend.bat"

REM 建立前端日誌監控腳本
echo @echo off > "%PROJECT_ROOT%\monitor_frontend.bat"
echo chcp 65001 ^> nul >> "%PROJECT_ROOT%\monitor_frontend.bat"
echo title 表單分析系統 - 前端日誌監控 >> "%PROJECT_ROOT%\monitor_frontend.bat"
echo cd /d "%SERVER_PATH%" >> "%PROJECT_ROOT%\monitor_frontend.bat"
echo echo ======================================== >> "%PROJECT_ROOT%\monitor_frontend.bat"
echo echo     前端應用日誌監控 >> "%PROJECT_ROOT%\monitor_frontend.bat"
echo echo ======================================== >> "%PROJECT_ROOT%\monitor_frontend.bat"
echo echo 前端應用 URL: http://localhost:18003/index.html >> "%PROJECT_ROOT%\monitor_frontend.bat"
echo echo ======================================== >> "%PROJECT_ROOT%\monitor_frontend.bat"
echo echo. >> "%PROJECT_ROOT%\monitor_frontend.bat"
echo docker-compose logs -f frontend >> "%PROJECT_ROOT%\monitor_frontend.bat"

REM 啟動兩個監控終端機
start "後端監控" /D "%PROJECT_ROOT%" monitor_backend.bat
timeout /t 2 /nobreak > nul
start "前端監控" /D "%PROJECT_ROOT%" monitor_frontend.bat

echo.
echo ========================================
echo             系統啟動完成！
echo ========================================
echo.
echo  服務連結：
echo     前端應用: http://localhost:18003/index.html
echo     API 文檔: http://localhost:18002/docs  
echo     API 測試: http://localhost:18002/redoc
echo     資料庫: localhost:18001 (PostgreSQL)
echo     資料庫管理: http://localhost:18004 (可選)
echo.
echo  服務狀態：
docker-compose ps

echo.
echo  已開啟監控終端機：
echo    後端監控 - 顯示 API 和資料庫日誌
echo    前端監控 - 顯示前端應用日誌
echo.
echo  常用指令：
echo     查看所有日誌: docker-compose logs -f
echo     停止服務: docker-compose down
echo     重啟服務: docker-compose restart
echo     健康檢查: docker-compose ps
echo.

REM 等待服務完全就緒
echo  最終健康檢查...
timeout /t 3 /nobreak > nul

REM 測試服務連通性
echo  測試服務連通性...
curl -s http://localhost:18002/healthz >nul 2>&1
if not errorlevel 1 (
    echo  後端 API 服務正常
) else (
    echo   後端 API 可能尚未完全就緒
)

curl -s http://localhost:18003 >nul 2>&1
if not errorlevel 1 (
    echo  前端應用服務正常
) else (
    echo   前端應用可能尚未完全就緒
)

echo.
set /p "open_browser= 是否立即開啟瀏覽器? (y/N): "
if /i "!open_browser!"=="y" (
    echo 正在開啟瀏覽器...
    start http://localhost:18003/index.html
    timeout /t 2 /nobreak > nul
    start http://localhost:18002/docs
)

echo 按任意鍵結束啟動程序...
pause > nul