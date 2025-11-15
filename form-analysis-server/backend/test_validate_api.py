"""
驗證結果 API 測試

測試 GET /api/validate API 端點的功能。
"""

import asyncio
import csv
import io
import requests
from datetime import datetime
from uuid import UUID

API_BASE_URL = "http://localhost:8000"


def create_test_csv_with_errors():
    """建立包含各種錯誤的測試 CSV 檔案"""
    
    test_data = [
        # 有效資料
        ["1234567_01", "測試產品A", "100", "2024-01-01"],
        ["2345678_02", "測試產品B", "200", "2024-01-02"],
        
        # 各種錯誤資料
        ["123456_01", "測試產品C", "300", "2024-01-03"],   # 批號格式錯誤
        ["3456789_03", "", "400", "2024-01-04"],          # 產品名稱為空
        ["4567890_04", "測試產品E", "-50", "2024-01-05"],   # 數量負數
        ["5678901_05", "測試產品F", "abc", "2024/01/06"],   # 數量非數字、日期格式錯誤
        ["", "測試產品G", "600", "2024-01-07"],           # 批號為空
        ["6789012_06", "測試產品H", "700", "invalid"],     # 日期無效
    ]
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["lot_no", "product_name", "quantity", "production_date"])
    
    for row in test_data:
        writer.writerow(row)
    
    content = output.getvalue()
    output.close()
    return content


def test_upload_and_get_process_id():
    """上傳檔案並獲取 process_id"""
    
    print("🧪 步驟 1: 上傳包含錯誤的測試檔案...")
    
    csv_content = create_test_csv_with_errors()
    
    try:
        files = {
            'file': ('test_errors.csv', csv_content, 'text/csv')
        }
        
        response = requests.post(f"{API_BASE_URL}/api/upload", files=files)
        
        print(f" 上傳回應狀態碼：{response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            process_id = result.get('process_id')
            print(f" 檔案上傳成功，Process ID: {process_id}")
            print(f"📈 統計：總行數 {result.get('total_rows')}, 有效 {result.get('valid_rows')}, 錯誤 {result.get('invalid_rows')}")
            return process_id
        else:
            print(f" 上傳失敗：{response.text}")
            return None
            
    except Exception as e:
        print(f" 上傳請求失敗：{e}")
        return None


def test_validate_api(process_id, page=1, page_size=10):
    """測試驗證結果 API"""
    
    print(f"\n🧪 步驟 2: 查詢驗證結果（頁 {page}，每頁 {page_size} 筆）...")
    
    try:
        params = {
            'process_id': process_id,
            'page': page,
            'page_size': page_size
        }
        
        response = requests.get(f"{API_BASE_URL}/api/validate", params=params)
        
        print(f" 驗證查詢狀態碼：{response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print(" 驗證結果查詢成功")
            print(f"📂 檔案：{result['filename']}")
            print(f"🏷️  狀態：{result['status']}")
            print(f" 建立時間：{result['created_at']}")
            
            # 統計資訊
            stats = result['statistics']
            print(f"\n 統計資訊：")
            print(f"   - 總行數：{stats['total_rows']}")
            print(f"   - 有效行數：{stats['valid_rows']}")
            print(f"   - 錯誤行數：{stats['invalid_rows']}")
            
            # 錯誤列表
            errors = result['errors']
            print(f"\n 錯誤項目（當前頁面 {len(errors)} 筆）：")
            for i, error in enumerate(errors, 1):
                print(f"   {i}. 行 {error['row_index']}, 欄位 '{error['field']}'")
                print(f"      錯誤代碼：{error['error_code']}")
                print(f"      訊息：{error['message']}")
                print()
            
            # 分頁資訊
            pagination = result['pagination']
            print(f" 分頁資訊：")
            print(f"   - 當前頁：{pagination['page']} / {pagination['total_pages']}")
            print(f"   - 每頁項目：{pagination['page_size']}")
            print(f"   - 總錯誤數：{pagination['total_errors']}")
            print(f"   - 有下一頁：{pagination['has_next']}")
            print(f"   - 有上一頁：{pagination['has_prev']}")
            
            return True
            
        elif response.status_code == 404:
            error_data = response.json()
            print(f" 找不到工作：{error_data}")
            return False
        else:
            print(f" 查詢失敗：{response.text}")
            return False
            
    except Exception as e:
        print(f" 查詢請求失敗：{e}")
        return False


def test_invalid_process_id():
    """測試無效的 process_id"""
    
    print(f"\n🧪 步驟 3: 測試無效的 process_id...")
    
    invalid_uuid = "00000000-0000-0000-0000-000000000000"
    
    try:
        params = {'process_id': invalid_uuid}
        response = requests.get(f"{API_BASE_URL}/api/validate", params=params)
        
        print(f" 無效 ID 查詢狀態碼：{response.status_code}")
        
        if response.status_code == 404:
            result = response.json()
            print(" 正確回傳 404 錯誤")
            print(f" 錯誤訊息：{result}")
            return True
        else:
            print(f" 未正確處理無效 ID：{response.text}")
            return False
            
    except Exception as e:
        print(f" 無效 ID 測試失敗：{e}")
        return False


def test_pagination(process_id):
    """測試分頁功能"""
    
    print(f"\n🧪 步驟 4: 測試分頁功能...")
    
    # 測試第一頁，每頁 3 筆
    success1 = test_validate_api(process_id, page=1, page_size=3)
    
    # 測試第二頁，每頁 3 筆
    if success1:
        print(f"\n--- 查詢第二頁 ---")
        success2 = test_validate_api(process_id, page=2, page_size=3)
        return success1 and success2
    
    return success1


def main():
    """主測試函數"""
    
    print(" 開始驗證結果 API 測試")
    print("時間：", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    # 檢查 API 連接
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code != 200:
            print(" API 伺服器未運行，請先啟動伺服器")
            return
    except Exception as e:
        print(f" 無法連接到 API 伺服器：{e}")
        print("請確保伺服器已啟動在 http://localhost:8000")
        return
    
    # 上傳檔案
    process_id = test_upload_and_get_process_id()
    if not process_id:
        print(" 無法獲取 process_id，測試終止")
        return
    
    # 測試基本查詢
    basic_test = test_validate_api(process_id)
    
    # 測試無效 ID
    invalid_id_test = test_invalid_process_id()
    
    # 測試分頁
    pagination_test = test_pagination(process_id)
    
    # 總結
    print("\n" + "=" * 60)
    print(" 測試結果總結：")
    print(f"   - 基本查詢：{' 成功' if basic_test else ' 失敗'}")
    print(f"   - 無效 ID 處理：{' 成功' if invalid_id_test else ' 失敗'}")
    print(f"   - 分頁功能：{' 成功' if pagination_test else ' 失敗'}")
    
    if all([basic_test, invalid_id_test, pagination_test]):
        print("\n🎊 所有測試通過！驗證結果 API 運作正常。")
        print(f" API 文檔：http://localhost:8000/docs")
        print(f"🔗 測試用的 Process ID：{process_id}")
    else:
        print("\n  部分測試失敗，請檢查 API 實作。")


if __name__ == "__main__":
    main()