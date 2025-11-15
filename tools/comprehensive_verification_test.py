#!/usr/bin/env python3
"""
Form Analysis System - 綜合驗證測試腳本

完整驗證系統所有組件的功能，包括：
1. 資料庫結構驗證
2. API 端點測試
3. 前端功能驗證
4. Docker 環境檢查

此腳本作為用戶接收測試的完整驗證工具。
"""

import os
import sys
import json
import time
import sqlite3
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
import io
import csv

# 測試結果計數器
test_results = {
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "warnings": 0
}

def print_header(title: str):
    """打印測試區塊標題"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_test(description: str):
    """打印測試描述"""
    print(f"\n🧪 測試: {description}")

def print_pass(message: str):
    """打印通過消息"""
    print(f" {message}")
    test_results["passed"] += 1

def print_fail(message: str):
    """打印失敗消息"""
    print(f" {message}")
    test_results["failed"] += 1

def print_skip(message: str):
    """打印跳過消息"""
    print(f"⏭️  {message}")
    test_results["skipped"] += 1

def print_warning(message: str):
    """打印警告消息"""
    print(f"  {message}")
    test_results["warnings"] += 1

def print_info(message: str):
    """打印信息消息"""
    print(f"  {message}")

def check_database_structure():
    """驗證資料庫結構"""
    print_header("資料庫結構驗證")
    
    db_path = Path(__file__).parent / "form-analysis-server" / "backend" / "dev_test.db"
    
    print_test("檢查資料庫文件是否存在")
    if db_path.exists():
        print_pass(f"資料庫文件存在: {db_path}")
    else:
        print_fail(f"資料庫文件不存在: {db_path}")
        return
    
    try:
        # 連接資料庫
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        print_test("驗證資料表結構")
        
        # 檢查 upload_jobs 表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='upload_jobs'
        """)
        if cursor.fetchone():
            print_pass("upload_jobs 表存在")
        else:
            print_fail("upload_jobs 表不存在")
        
        # 檢查 upload_errors 表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='upload_errors'
        """)
        if cursor.fetchone():
            print_pass("upload_errors 表存在")
        else:
            print_fail("upload_errors 表不存在")
        
        # 檢查 records 表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='records'
        """)
        if cursor.fetchone():
            print_pass("records 表存在")
        else:
            print_fail("records 表不存在")
        
        # 檢查 upload_jobs 表結構
        print_test("驗證 upload_jobs 表字段")
        cursor.execute("PRAGMA table_info(upload_jobs)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = ['id', 'filename', 'created_at', 'status', 'total_rows', 'valid_rows', 'invalid_rows', 'process_id']
        
        for col in expected_columns:
            if col in columns:
                print_pass(f"upload_jobs.{col} 字段存在")
            else:
                print_fail(f"upload_jobs.{col} 字段不存在")
        
        # 檢查索引
        print_test("驗證索引結構")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='upload_jobs'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        if any('process_id' in idx for idx in indexes):
            print_pass("upload_jobs.process_id 索引存在")
        else:
            print_warning("upload_jobs.process_id 索引可能不存在")
        
        conn.close()
        
    except Exception as e:
        print_fail(f"資料庫驗證失敗: {e}")

def test_api_endpoints():
    """測試 API 端點"""
    print_header("API 端點測試")
    
    # 假設服務運行在 8001 端口
    base_url = "http://localhost:8001"
    
    print_test("測試基本健康檢查")
    try:
        response = requests.get(f"{base_url}/healthz", timeout=5)
        if response.status_code == 200:
            print_pass("健康檢查端點正常")
            print_info(f"回應: {response.json()}")
        else:
            print_fail(f"健康檢查失敗，狀態碼: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print_skip("無法連接到 API 服務，請確保服務正在運行")
        return
    except Exception as e:
        print_fail(f"健康檢查異常: {e}")
        return
    
    print_test("測試根端點")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print_pass("根端點正常")
            print_info(f"回應: {response.json()}")
        else:
            print_fail(f"根端點失敗，狀態碼: {response.status_code}")
    except Exception as e:
        print_fail(f"根端點測試異常: {e}")
    
    print_test("測試文件上傳端點")
    try:
        # 創建測試 CSV 文件
        csv_content = """lot_no,product_name,quantity,production_date
1234567_01,測試產品A,100,2024-01-15
2345678_02,測試產品B,50,2024-01-16
3456789_03,測試產品C,75,2024-01-17
"""
        
        files = {'file': ('test.csv', csv_content, 'text/csv')}
        response = requests.post(f"{base_url}/api/upload", files=files, timeout=10)
        
        if response.status_code == 200:
            upload_result = response.json()
            print_pass("文件上傳端點正常")
            print_info(f"上傳結果: {upload_result}")
            
            # 獲取 process_id 用於後續測試
            process_id = upload_result.get('process_id')
            if process_id:
                test_validation_endpoint(base_url, process_id)
                test_import_endpoint(base_url, process_id)
                test_export_endpoint(base_url, process_id)
        else:
            print_fail(f"文件上傳失敗，狀態碼: {response.status_code}")
            print_info(f"錯誤回應: {response.text}")
            
    except Exception as e:
        print_fail(f"文件上傳測試異常: {e}")

def test_validation_endpoint(base_url: str, process_id: str):
    """測試驗證端點"""
    print_test("測試驗證查詢端點")
    try:
        response = requests.get(f"{base_url}/api/validate?process_id={process_id}", timeout=5)
        if response.status_code == 200:
            print_pass("驗證查詢端點正常")
            validation_result = response.json()
            print_info(f"驗證結果: {validation_result}")
        else:
            print_fail(f"驗證查詢失敗，狀態碼: {response.status_code}")
    except Exception as e:
        print_fail(f"驗證查詢測試異常: {e}")

def test_import_endpoint(base_url: str, process_id: str):
    """測試匯入端點"""
    print_test("測試資料匯入端點")
    try:
        import_data = {"process_id": process_id}
        response = requests.post(f"{base_url}/api/import", json=import_data, timeout=10)
        if response.status_code == 200:
            print_pass("資料匯入端點正常")
            import_result = response.json()
            print_info(f"匯入結果: {import_result}")
        else:
            print_warning(f"資料匯入狀態碼: {response.status_code}")
            print_info(f"回應: {response.text}")
    except Exception as e:
        print_fail(f"資料匯入測試異常: {e}")

def test_export_endpoint(base_url: str, process_id: str):
    """測試匯出端點"""
    print_test("測試錯誤匯出端點")
    try:
        response = requests.get(f"{base_url}/api/errors.csv?process_id={process_id}", timeout=5)
        if response.status_code == 200:
            print_pass("錯誤匯出端點正常")
            print_info(f"CSV 內容長度: {len(response.text)} 字元")
        elif response.status_code == 404:
            print_warning("沒有找到錯誤資料（正常情況，如果沒有錯誤）")
        else:
            print_fail(f"錯誤匯出失敗，狀態碼: {response.status_code}")
    except Exception as e:
        print_fail(f"錯誤匯出測試異常: {e}")

def check_frontend_files():
    """檢查前端文件"""
    print_header("前端文件驗證")
    
    frontend_path = Path(__file__).parent / "form-analysis-server" / "frontend"
    
    print_test("檢查前端目錄結構")
    if frontend_path.exists():
        print_pass(f"前端目錄存在: {frontend_path}")
    else:
        print_fail(f"前端目錄不存在: {frontend_path}")
        return
    
    # 檢查關鍵文件
    key_files = [
        "package.json",
        "vite.config.ts",
        "index.html",
        "src/App.tsx",
        "src/pages/Upload.tsx"
    ]
    
    for file in key_files:
        file_path = frontend_path / file
        if file_path.exists():
            print_pass(f"{file} 存在")
        else:
            print_fail(f"{file} 不存在")

def check_upload_component():
    """檢查 Upload 組件內容"""
    print_test("驗證 Upload 組件實現")
    
    upload_file = Path(__file__).parent / "form-analysis-server" / "frontend" / "src" / "pages" / "Upload.tsx"
    
    if not upload_file.exists():
        print_fail("Upload.tsx 文件不存在")
        return
    
    try:
        content = upload_file.read_text(encoding='utf-8')
        
        # 檢查關鍵功能
        checks = [
            ("檔案上傳功能", "useCallback" in content and "FormData" in content),
            ("拖放功能", "onDrop" in content and "onDragOver" in content),
            ("進度顯示", "progress" in content.lower()),
            ("錯誤處理", "error" in content.lower() and "catch" in content),
            ("API 呼叫", "fetch" in content or "axios" in content),
            ("Toast 通知", "toast" in content.lower()),
            ("檔案驗證", "validation" in content.lower() or "validate" in content.lower()),
            ("匯入確認", "import" in content.lower() and "confirm" in content.lower())
        ]
        
        for check_name, condition in checks:
            if condition:
                print_pass(f"{check_name} 已實現")
            else:
                print_warning(f"{check_name} 可能未完全實現")
                
    except Exception as e:
        print_fail(f"讀取 Upload.tsx 失敗: {e}")

def check_docker_setup():
    """檢查 Docker 配置"""
    print_header("Docker 配置驗證")
    
    backend_path = Path(__file__).parent / "form-analysis-server" / "backend"
    frontend_path = Path(__file__).parent / "form-analysis-server" / "frontend"
    root_path = Path(__file__).parent / "form-analysis-server"
    
    print_test("檢查 Docker 配置文件")
    
    # 檢查 Docker 文件
    docker_files = [
        (root_path / "docker-compose.yml", "Docker Compose 配置"),
        (backend_path / "Dockerfile", "後端 Dockerfile"),
        (frontend_path / "Dockerfile", "前端 Dockerfile"),
    ]
    
    for file_path, description in docker_files:
        if file_path.exists():
            print_pass(f"{description} 存在")
        else:
            print_fail(f"{description} 不存在")

def check_environment_files():
    """檢查環境配置文件"""
    print_test("檢查環境配置")
    
    backend_path = Path(__file__).parent / "form-analysis-server" / "backend"
    
    env_files = [
        (".env", "環境配置文件"),
        (".env.dev", "開發環境配置"),
        ("alembic.ini", "Alembic 配置")
    ]
    
    for file, description in env_files:
        file_path = backend_path / file
        if file_path.exists():
            print_pass(f"{description} 存在")
            
            # 檢查 .env 文件內容
            if file == ".env":
                try:
                    content = file_path.read_text()
                    if "DATABASE_URL" in content:
                        print_pass("資料庫連接配置存在")
                    if "SECRET_KEY" in content:
                        print_pass("安全密鑰配置存在")
                    if "API_PORT" in content:
                        print_pass("API 端口配置存在")
                except Exception as e:
                    print_warning(f"讀取 {file} 失敗: {e}")
        else:
            print_fail(f"{description} 不存在")

def check_backend_models():
    """檢查後端模型定義"""
    print_test("檢查資料模型定義")
    
    models_path = Path(__file__).parent / "form-analysis-server" / "backend" / "app" / "models"
    
    model_files = [
        "upload_job.py",
        "upload_error.py", 
        "record.py"
    ]
    
    for model_file in model_files:
        file_path = models_path / model_file
        if file_path.exists():
            print_pass(f"{model_file} 模型存在")
        else:
            print_fail(f"{model_file} 模型不存在")

def print_summary():
    """打印測試摘要"""
    print_header("測試結果摘要")
    
    total = sum(test_results.values())
    
    print(f" 測試統計:")
    print(f"    通過: {test_results['passed']}")
    print(f"    失敗: {test_results['failed']}")
    print(f"   ⏭️  跳過: {test_results['skipped']}")
    print(f"     警告: {test_results['warnings']}")
    print(f"   📝 總計: {total}")
    
    if test_results['failed'] == 0:
        print(f"\n🎉 恭喜！所有關鍵測試都通過了！")
        if test_results['warnings'] > 0:
            print(f"  注意: 有 {test_results['warnings']} 個警告項目需要關注")
    else:
        print(f"\n  有 {test_results['failed']} 個測試失敗，需要修復")
    
    # 使用建議
    print(f"\n📋 使用建議:")
    if test_results['failed'] > 0:
        print("   1. 修復失敗的測試項目")
        print("   2. 確保後端服務正在運行（端口 8001）")
        print("   3. 檢查資料庫遷移是否完成")
    
    print("   4. 啟動前端開發服務器：npm run dev")
    print("   5. 開啟瀏覽器訪問 http://localhost:5173")
    print("   6. 測試完整的檔案上傳流程")

def main():
    """主測試函數"""
    print("🚀 Form Analysis System - 綜合驗證測試")
    print("=" * 60)
    
    # 執行各項測試
    check_database_structure()
    check_backend_models()
    check_environment_files()
    test_api_endpoints()
    check_frontend_files()
    check_upload_component()
    check_docker_setup()
    
    # 打印摘要
    print_summary()
    
    return test_results['failed'] == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)