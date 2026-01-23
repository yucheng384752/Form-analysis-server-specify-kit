@echo off 
chcp 65001 > nul 
title 表單分析系統 - 後端日誌監控 
cd /d "C:\Users\yucheng\Desktop\Form-analysis-server-specify-kit\form-analysis-server" 
echo ======================================== 
echo     後端 API 服務日誌監控 
echo ======================================== 
echo 後端服務 URL: http://localhost:18002 
echo API 文檔: http://localhost:18002/docs 
echo ======================================== 
echo. 
docker-compose logs -f backend db 
