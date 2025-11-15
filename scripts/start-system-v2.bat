@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
echo.
echo ========================================
echo     表單分析系統 - 啟動腳本 v2.0
echo ========================================
echo.

REM 設置工作目錄
cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

echo  項目路徑設定:
echo    根目錄: %PROJECT_ROOT%
echo    服務器: %SERVER_PATH%
echo.

REM 檢查 Docker Desktop 是否正在運行
echo [1/7] 檢查 Docker Desktop 狀態...
docker --version >nul 2>&1
if errorlevel 1 (
    echo  Docker 未安裝
    echo    請安裝 Docker Desktop
    pause
    exit /b 1
)

REM 檢查 Docker daemon 是否運行
docker ps >nul 2>&1
if errorlevel 1 (
    echo   Docker Desktop 未啟動，嘗試自動啟動...
    
    REM 檢查 Docker Desktop 是否已安裝
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
        echo     啟動 Docker Desktop...
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    ) else if exist "%USERPROFILE%\AppData\Local\Docker\Docker Desktop.exe" (
        echo     啟動 Docker Desktop...
        start "" "%USERPROFILE%\AppData\Local\Docker\Docker Desktop.exe"
    ) else (
        echo  找不到 Docker Desktop 安裝路徑
        echo    請手動啟動 Docker Desktop 或重新安裝
        pause
        exit /b 1
    )
    
    echo     等待 Docker Desktop 啟動...
    set /a timeout_counter=0
    :docker_wait
    set /a timeout_counter+=1
    timeout /t 5 /nobreak >nul
    
    docker ps >nul 2>&1
    if not errorlevel 1 (
        echo  Docker Desktop 已啟動
        goto docker_ready
    )
    
    if !timeout_counter! geq 24 (
        echo  Docker Desktop 啟動超時（等待 2 分鐘）
        echo    請手動啟動 Docker Desktop 並重新執行此腳本
        pause
        exit /b 1
    )
    
    echo     等待中... (!timeout_counter!/24)
    goto docker_wait
) else (
    echo  Docker 服務正常運行
)

:docker_ready

REM 檢查 Docker Compose 是否可用
echo [2/7] 檢查 Docker Compose...
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose --version >nul 2>&1
    if errorlevel 1 (
        echo  Docker Compose 未安裝或不可用
        echo    請確保 Docker Compose 已正確安裝
        pause
        exit /b 1
    ) else (
        echo  Docker Compose ^(V2^) 可用
        set "DOCKER_COMPOSE=docker compose"
    )
) else (
    echo  Docker Compose ^(V1^) 可用
    set "DOCKER_COMPOSE=docker-compose"
)

REM 檢查 docker-compose 檔案
echo [3/7] 檢查配置檔案...
echo  檢查路徑: %SERVER_PATH%\docker-compose.yml
if not exist "%SERVER_PATH%\docker-compose.yml" (
    echo  找不到 docker-compose.yml 檔案
    echo    預期路徑: %SERVER_PATH%\docker-compose.yml
    echo    項目根目錄: %PROJECT_ROOT%
    echo    
    echo  當前目錄結構:
    dir "%PROJECT_ROOT%" /B
    echo.
    echo  請確認:
    echo    1. 您在正確的專案目錄中
    echo    2. docker-compose.yml 檔案存在於 form-analysis-server 目錄下
    pause
    exit /b 1
) else (
    echo  找到 docker-compose.yml 檔案
)

REM 檢查後端 Dockerfile
if not exist "%SERVER_PATH%\backend\Dockerfile" (
    echo   警告: 找不到後端 Dockerfile
    echo    路徑: %SERVER_PATH%\backend\Dockerfile
) else (
    echo  後端 Dockerfile 存在
)

REM 檢查前端 Dockerfile
if not exist "%SERVER_PATH%\frontend\Dockerfile" (
    echo   警告: 找不到前端 Dockerfile
    echo    路徑: %SERVER_PATH%\frontend\Dockerfile
) else (
    echo  前端 Dockerfile 存在
)

REM 切換到服務器目錄
cd /d "%SERVER_PATH%"

REM 預先診斷常見問題
echo.
echo [4/7] 預先診斷檢查...

REM 檢查端口佔用
set "port_conflict=false"
netstat -an | find ":5432" | find "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   檢測到端口 5432 PostgreSQL 被佔用，將自動清理
    set "port_conflict=true"
)

netstat -an | find ":8000" | find "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   檢測到端口 8000 API 被佔用，將自動清理
    set "port_conflict=true"
)

netstat -an | find ":5173" | find "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   檢測到端口 5173 前端被佔用，將自動清理
    set "port_conflict=true"
)

if "!port_conflict!"=="true" (
    echo     執行額外清理以釋放端口...
    %DOCKER_COMPOSE% down -v --remove-orphans >nul 2>&1
    timeout /t 3 /nobreak >nul
) else (
    echo     端口檢查完成，無衝突
)

echo.
echo [5/7] 停止現有容器並清理...
%DOCKER_COMPOSE% down --remove-orphans --volumes
if errorlevel 1 (
    echo   清理容器時遇到問題，繼續執行...
)

echo.
echo [6/7] 建立並啟動所有服務...
echo     這可能需要幾分鐘時間，特別是首次執行時...

%DOCKER_COMPOSE% up -d --build
if errorlevel 1 (
    echo  服務啟動失敗，查看詳細日誌:
    %DOCKER_COMPOSE% logs --tail=50
    echo.
    echo  常見問題排除:
    echo    1. 確認 Docker Desktop 有足夠資源 (RAM: 4GB+, Disk: 2GB+)
    echo    2. 檢查網路連線 (需要下載 Docker 映像)
    echo    3. 確認 docker-compose.yml 語法正確
    echo    4. 檢查是否有防火牆或防毒軟體阻擋
    pause
    exit /b 1
)

echo.
echo [7/7] 等待服務健康檢查...
set /a overall_counter=0
:health_check_loop
set /a overall_counter+=1

REM 檢查所有服務狀態
%DOCKER_COMPOSE% ps --format table >nul 2>&1
if errorlevel 1 (
    echo  無法檢查服務狀態
    goto health_check_failed
)

REM 檢查各服務健康狀態
set "db_healthy=false"
set "backend_healthy=false"
set "frontend_healthy=false"

REM 檢查資料庫
%DOCKER_COMPOSE% ps db --format "table {{.Status}}" | find "healthy" >nul 2>&1
if not errorlevel 1 set "db_healthy=true"

REM 檢查後端
%DOCKER_COMPOSE% ps backend --format "table {{.Status}}" | find "healthy" >nul 2>&1
if not errorlevel 1 set "backend_healthy=true"

REM 檢查前端
%DOCKER_COMPOSE% ps frontend --format "table {{.Status}}" | find "healthy" >nul 2>&1
if not errorlevel 1 set "frontend_healthy=true"

REM 顯示進度
echo     健康檢查進行中... (!overall_counter!/60)
echo     資料庫: !db_healthy! ^| 後端: !backend_healthy! ^| 前端: !frontend_healthy!

REM 如果所有服務都健康，跳出迴圈
if "!db_healthy!"=="true" if "!backend_healthy!"=="true" if "!frontend_healthy!"=="true" (
    echo  所有服務健康檢查通過！
    goto all_services_ready
)

REM 超時檢查
if !overall_counter! geq 60 (
    echo  健康檢查超時（等待 5 分鐘）
    goto health_check_failed
)

timeout /t 5 /nobreak > nul
goto health_check_loop

:health_check_failed
echo.
echo  當前服務狀態：
%DOCKER_COMPOSE% ps

echo.
echo  詳細日誌：
%DOCKER_COMPOSE% logs --tail=20

echo.
echo  建議檢查：
echo    1. 檢查系統資源（CPU/記憶體）
echo    2. 重新啟動 Docker Desktop
echo    3. 檢查網路連線
echo    4. 清理 Docker 快取: docker system prune
pause
exit /b 1

:all_services_ready

echo.
echo ========================================
echo             系統啟動完成！
echo ========================================
echo.
echo  服務連結：
echo     前端應用: http://localhost:5173
echo     API 文檔: http://localhost:8000/docs  
echo     API 測試: http://localhost:8000/redoc
echo.
echo  服務狀態：
%DOCKER_COMPOSE% ps

echo.
echo  測試服務連通性...
timeout /t 3 /nobreak > nul

curl -s http://localhost:8000/healthz >nul 2>&1
if not errorlevel 1 (
    echo  後端 API 服務正常 (http://localhost:8000)
) else (
    echo   後端 API 可能尚未完全就緒
)

curl -s http://localhost:5173 >nul 2>&1
if not errorlevel 1 (
    echo  前端應用服務正常 (http://localhost:5173)
) else (
    echo   前端應用可能尚未完全就緒
)

echo.
echo  常用指令：
echo     查看日誌: %DOCKER_COMPOSE% logs -f
echo     停止服務: %DOCKER_COMPOSE% down
echo     重啟服務: %DOCKER_COMPOSE% restart
echo     健康檢查: %DOCKER_COMPOSE% ps
echo    📂 開啟日誌監控: %DOCKER_COMPOSE% logs -f backend frontend db
echo.

set /p "open_browser= 是否立即開啟瀏覽器? (y/N): "
if /i "!open_browser!"=="y" (
    echo 正在開啟瀏覽器...
    start http://localhost:5173
    timeout /t 2 /nobreak > nul
    start http://localhost:8000/docs
)

set /p "open_logs= 是否開啟日誌監控? (y/N): "
if /i "!open_logs!"=="y" (
    echo 正在開啟日誌監控...
    start "系統日誌監控" cmd /k "cd /d "%SERVER_PATH%" && %DOCKER_COMPOSE% logs -f"
)

echo.
echo  提示：
echo    - 服務將在背景持續運行
echo    - 要停止所有服務，請執行: %DOCKER_COMPOSE% down
echo    - 服務啟動後，通常需要 1-2 分鐘才能完全準備就緒
echo.
echo 按任意鍵結束啟動程序...
pause > nul

REM 返回原始目錄
cd /d "%PROJECT_ROOT%\scripts"