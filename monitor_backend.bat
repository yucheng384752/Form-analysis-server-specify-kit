@echo off 
chcp 65001 > nul 
title 表單分析系統 - 後端日誌監控 
cd /d "C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server" 
echo ======================================== 
echo     後端 API 服務日誌監控 
echo ======================================== 
echo 後端服務 URL: http://localhost:8000 
echo API 文檔: http://localhost:8000/docs 
echo ======================================== 
echo. 
docker-compose logs -f backend db 
