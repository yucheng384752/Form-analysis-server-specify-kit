@echo off 
chcp 65001 > nul 
title 表單分析系統 - 前端日誌監控 
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%form-analysis-server" 
echo ======================================== 
echo     前端應用日誌監控 
echo ======================================== 
echo 前端應用 URL: http://localhost:18003/index.html 
echo ======================================== 
echo. 
docker-compose logs -f frontend 
