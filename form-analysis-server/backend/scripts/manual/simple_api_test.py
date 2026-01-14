"""
簡單的 API 連通性測試

測試基本的 API 連接而不需要複雜的異步設置。
"""

import requests
import csv
import io
from datetime import datetime

API_BASE_URL = "http://localhost:8000"

def test_api_connection():
    """測試 API 基本連接"""
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            print(" API 連接成功")
            print(f" 回應：{response.json()}")
            return True
        else:
            print(f" API 連接失敗：{response.status_code}")
            return False
    except Exception as e:
        print(f" 無法連接到 API：{e}")
        return False

def test_api_docs():
    """測試 API 文檔"""
    try:
        response = requests.get(f"{API_BASE_URL}/docs")
        if response.status_code == 200:
            print(" API 文檔可訪問")
            return True
        else:
            print(f" API 文檔無法訪問：{response.status_code}")
            return False
    except Exception as e:
        print(f" 文檔訪問錯誤：{e}")
        return False

def create_test_csv_file():
    """建立測試用的 CSV 檔案"""
    test_data = [
        ["1234567_01", "測試產品A", "100", "2024-01-01"],
        ["2345678_02", "測試產品B", "200", "2024-01-02"],
    ]
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["lot_no", "product_name", "quantity", "production_date"])
    
    for row in test_data:
        writer.writerow(row)
    
    content = output.getvalue()
    output.close()
    return content

def test_file_upload():
    """測試檔案上傳"""
    print("\n測試檔案上傳...")
    
    csv_content = create_test_csv_file()
    
    try:
        files = {
            'file': ('test.csv', csv_content, 'text/csv')
        }
        
        response = requests.post(f"{API_BASE_URL}/api/upload", files=files)
        
        print(f" HTTP 狀態碼：{response.status_code}")
        print(f" 回應內容：{response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(" 檔案上傳成功")
            return result.get('process_id')
        else:
            print(f" 檔案上傳失敗")
            return None
            
    except Exception as e:
        print(f" 上傳請求失敗：{e}")
        return None

def test_upload_status(process_id):
    """測試狀態查詢"""
    if not process_id:
        return False
        
    print(f"\n測試狀態查詢 (Process ID: {process_id})...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/upload/{process_id}/status")
        
        print(f" HTTP 狀態碼：{response.status_code}")
        print(f" 回應內容：{response.text}")
        
        if response.status_code == 200:
            print(" 狀態查詢成功")
            return True
        else:
            print(f" 狀態查詢失敗")
            return False
            
    except Exception as e:
        print(f" 狀態查詢請求失敗：{e}")
        return False

def main():
    """主測試函數"""
    print(" 開始簡單 API 測試")
    print("時間：", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 50)
    
    # 測試基本連接
    connection_ok = test_api_connection()
    if not connection_ok:
        print("\n API 伺服器未啟動，請先執行:")
        print("   python app/main.py")
        return
    
    # 測試文檔
    docs_ok = test_api_docs()
    
    # 測試檔案上傳
    process_id = test_file_upload()
    upload_ok = process_id is not None
    
    # 測試狀態查詢
    status_ok = test_upload_status(process_id)
    
    # 總結
    print("\n" + "=" * 50)
    print(" 測試結果總結：")
    print(f"   - API 連接：{' 成功' if connection_ok else ' 失敗'}")
    print(f"   - API 文檔：{' 成功' if docs_ok else ' 失敗'}")
    print(f"   - 檔案上傳：{' 成功' if upload_ok else ' 失敗'}")
    print(f"   - 狀態查詢：{' 成功' if status_ok else ' 失敗'}")
    
    if all([connection_ok, docs_ok, upload_ok, status_ok]):
        print("\n🎊 所有測試通過！檔案上傳 API 運作正常。")
        print(" 訪問 http://localhost:8000/docs 查看完整 API 文檔")
    else:
        print("\n  部分測試失敗，請檢查伺服器狀態。")

if __name__ == "__main__":
    main()