#!/usr/bin/env python3
"""
快速啟動腳本 - 同時啟動前後端服務

用法：
python quick_start.py

這將會：
1. 啟動後端 API 服務 (端口 8000)
2. 啟動前端開發服務器 (端口 5173)
3. 自動打開瀏覽器到 http://localhost:5173
"""

import os
import sys
import time
import subprocess
import webbrowser
from pathlib import Path

def print_status(message):
    """打印狀態消息"""
    print(f" {message}")

def print_success(message):
    """打印成功消息"""
    print(f" {message}")

def print_error(message):
    """打印錯誤消息"""
    print(f" {message}")

def start_backend():
    """啟動後端服務"""
    print_status("正在啟動後端服務...")
    
    # 獲取後端目錄
    backend_dir = Path(__file__).parent / "form-analysis-server" / "backend"
    
    if not backend_dir.exists():
        print_error(f"後端目錄不存在: {backend_dir}")
        return None
    
    # 檢查虛擬環境
    venv_python = backend_dir / "venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        print_error("虛擬環境不存在，請先運行 python -m venv venv")
        return None
    
    # 檢查 app 模塊
    app_dir = backend_dir / "app"
    if not app_dir.exists():
        print_error(f"App 模塊不存在: {app_dir}")
        return None
    
    # 設置環境變量
    env = os.environ.copy()
    env['PYTHONPATH'] = str(backend_dir)
    
    # 啟動命令
    cmd = [
        str(venv_python),
        "-c",
        "import sys; sys.path.insert(0, '.'); from app.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8000)"
    ]
    
    try:
        # 啟動後端進程
        process = subprocess.Popen(
            cmd,
            cwd=str(backend_dir),
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        
        print_success("後端服務已啟動 (端口 8000)")
        return process
        
    except Exception as e:
        print_error(f"啟動後端服務失敗: {e}")
        return None

def start_frontend():
    """啟動前端服務"""
    print_status("正在啟動前端服務...")
    
    # 獲取前端目錄
    frontend_dir = Path(__file__).parent / "form-analysis-server" / "frontend"
    
    if not frontend_dir.exists():
        print_error(f"前端目錄不存在: {frontend_dir}")
        return None
    
    # 檢查 package.json
    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        print_error(f"package.json 不存在: {package_json}")
        return None
    
    try:
        # 啟動前端進程
        process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(frontend_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        
        print_success("前端服務已啟動 (端口 5173)")
        return process
        
    except Exception as e:
        print_error(f"啟動前端服務失敗: {e}")
        return None

def test_services():
    """測試服務是否正常"""
    print_status("等待服務啟動...")
    time.sleep(5)
    
    # 測試後端
    try:
        import requests
        response = requests.get("http://localhost:8000/healthz", timeout=5)
        if response.status_code == 200:
            print_success("後端 API 服務正常")
        else:
            print_error(f"後端 API 服務異常，狀態碼: {response.status_code}")
    except Exception as e:
        print_error(f"無法連接後端服務: {e}")
    
    # 測試前端
    try:
        import requests
        response = requests.get("http://localhost:5173", timeout=5)
        if response.status_code == 200:
            print_success("前端服務正常")
        else:
            print_error(f"前端服務異常，狀態碼: {response.status_code}")
    except Exception as e:
        print_error(f"無法連接前端服務: {e}")

def main():
    """主函數"""
    print(" Form Analysis System - 快速啟動")
    print("=" * 50)
    
    # 檢查是否安裝了 requests
    try:
        import requests
    except ImportError:
        print_status("正在安裝 requests...")
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"])
    
    # 啟動後端
    backend_process = start_backend()
    if not backend_process:
        print_error("後端啟動失敗，退出...")
        return 1
    
    # 等待一下讓後端啟動
    time.sleep(2)
    
    # 啟動前端
    frontend_process = start_frontend()
    if not frontend_process:
        print_error("前端啟動失敗，但後端仍在運行...")
        return 1
    
    # 測試服務
    test_services()
    
    # 打開瀏覽器
    print_status("正在打開瀏覽器...")
    webbrowser.open("http://localhost:5173")
    
    print("\n" + "=" * 50)
    print(" 服務已啟動！")
    print(" 後端 API: http://localhost:8000")
    print(" 前端界面: http://localhost:5173")
    print(" API 文檔: http://localhost:8000/docs")
    print("\n按 Ctrl+C 停止服務")
    print("=" * 50)
    
    # 保持運行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n 正在停止服務...")
        if backend_process:
            backend_process.terminate()
        if frontend_process:
            frontend_process.terminate()
        print(" 服務已停止")
        return 0

if __name__ == "__main__":
    sys.exit(main())