#!/usr/bin/env python3
"""
簡單的P1/P2/P3測試資料創建腳本

使用curl調用API創建測試數據
"""

import subprocess
import json

def create_test_data_via_api():
    """通過API創建測試資料"""
    print(" 開始通過API創建 P1/P2/P3 測試資料")
    print("=" * 50)
    
    # API端點
    api_url = "http://localhost:8000/api/query/records/create-test-data"
    
    try:
        # 調用API創建測試資料
        result = subprocess.run([
            "curl", "-X", "POST", api_url,
            "-H", "Content-Type: application/json"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            response = json.loads(result.stdout)
            print(f" API調用成功: {response}")
        else:
            print(f" API調用失敗: {result.stderr}")
            print(f"stdout: {result.stdout}")
            
    except subprocess.TimeoutExpired:
        print(" API調用超時")
    except json.JSONDecodeError as e:
        print(f" JSON解析錯誤: {e}")
        print(f"原始回應: {result.stdout}")
    except Exception as e:
        print(f" 意外錯誤: {e}")

if __name__ == "__main__":
    create_test_data_via_api()