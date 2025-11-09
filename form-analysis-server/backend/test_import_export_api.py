"""
匯入和匯出 API 測試

測試 POST /api/import 和 GET /api/errors.csv API 端點的功能。
"""

import requests
import csv
import io
from datetime import datetime

API_BASE_URL = "http://localhost:8000"


def create_test_csv_with_errors():
    """建立包含各種錯誤的測試 CSV 檔案"""
    
    test_data = [
        # 有效資料
        ["1234567_01", "測試產品A", "100", "2024-01-01"],
        ["2345678_02", "測試產品B", "200", "2024-01-02"],
        ["3456789_03", "測試產品C", "300", "2024-01-03"],
        
        # 錯誤資料
        ["123456_01", "測試產品D", "400", "2024-01-04"],   # 批號格式錯誤
        ["4567890_04", "", "500", "2024-01-05"],          # 產品名稱為空
        ["5678901_05", "測試產品F", "-50", "2024-01-06"],  # 數量負數
        ["6789012_06", "測試產品G", "abc", "2024/01/07"],  # 數量非數字、日期格式錯誤
        ["", "測試產品H", "600", "invalid-date"],         # 批號為空、日期無效
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
            'file': ('test_import_export.csv', csv_content, 'text/csv')
        }
        
        response = requests.post(f"{API_BASE_URL}/api/upload", files=files)
        
        if response.status_code == 200:
            result = response.json()
            process_id = result.get('process_id')
            print(f"✅ 檔案上傳成功，Process ID: {process_id}")
            print(f"📈 統計：總 {result.get('total_rows')}，有效 {result.get('valid_rows')}，錯誤 {result.get('invalid_rows')}")
            return process_id
        else:
            print(f"❌ 上傳失敗：{response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 上傳請求失敗：{e}")
        return None


def test_import_api(process_id):
    """測試資料匯入 API"""
    
    print(f"\n🧪 步驟 2: 測試資料匯入...")
    
    try:
        data = {"process_id": process_id}
        
        response = requests.post(
            f"{API_BASE_URL}/api/import",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📊 匯入回應狀態碼：{response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 資料匯入成功")
            print(f"📈 匯入結果：")
            print(f"   - 成功匯入：{result['imported_rows']} 筆")
            print(f"   - 跳過錯誤：{result['skipped_rows']} 筆")
            print(f"   - 處理耗時：{result['elapsed_ms']} ms")
            print(f"   - 訊息：{result['message']}")
            return True
            
        elif response.status_code == 400:
            error_data = response.json()
            print(f"⚠️ 匯入錯誤：{error_data}")
            return False
        elif response.status_code == 404:
            error_data = response.json()
            print(f"❌ 找不到工作：{error_data}")
            return False
        else:
            print(f"❌ 匯入失敗：{response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 匯入請求失敗：{e}")
        return False


def test_export_errors_csv(process_id):
    """測試錯誤匯出 CSV API"""
    
    print(f"\n🧪 步驟 3: 測試錯誤匯出 CSV...")
    
    try:
        params = {"process_id": process_id}
        
        response = requests.get(
            f"{API_BASE_URL}/api/errors.csv",
            params=params
        )
        
        print(f"📊 匯出回應狀態碼：{response.status_code}")
        
        if response.status_code == 200:
            # 檢查回應標頭
            content_type = response.headers.get('content-type', '')
            content_disposition = response.headers.get('content-disposition', '')
            
            print("✅ CSV 匯出成功")
            print(f"📄 Content-Type: {content_type}")
            print(f"📎 Content-Disposition: {content_disposition}")
            
            # 解析 CSV 內容
            csv_content = response.text
            print(f"\n📋 CSV 內容預覽：")
            
            lines = csv_content.strip().split('\n')
            for i, line in enumerate(lines[:6]):  # 只顯示前6行
                if i == 0:
                    print(f"   標題: {line}")
                else:
                    print(f"   行{i}: {line}")
            
            if len(lines) > 6:
                print(f"   ... 還有 {len(lines) - 6} 行")
            
            print(f"\n📊 CSV 統計：")
            print(f"   - 總行數：{len(lines)} (包含標題)")
            print(f"   - 錯誤筆數：{len(lines) - 1}")
            
            return True
            
        elif response.status_code == 404:
            error_data = response.json()
            print(f"❌ 找不到工作：{error_data}")
            return False
        else:
            print(f"❌ 匯出失敗：{response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 匯出請求失敗：{e}")
        return False


def test_import_already_imported(process_id):
    """測試重複匯入檢查"""
    
    print(f"\n🧪 步驟 4: 測試重複匯入檢查...")
    
    try:
        data = {"process_id": process_id}
        
        response = requests.post(
            f"{API_BASE_URL}/api/import",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📊 重複匯入回應狀態碼：{response.status_code}")
        
        if response.status_code == 400:
            error_data = response.json()
            if error_data.get("detail", {}).get("error_code") == "JOB_ALREADY_IMPORTED":
                print("✅ 正確阻止重複匯入")
                print(f"📝 錯誤訊息：{error_data}")
                return True
            else:
                print(f"❌ 錯誤類型不符：{error_data}")
                return False
        else:
            print(f"❌ 應該要回傳 400 錯誤：{response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 重複匯入測試失敗：{e}")
        return False


def test_invalid_process_id_apis():
    """測試無效 process_id 的處理"""
    
    print(f"\n🧪 步驟 5: 測試無效 process_id...")
    
    invalid_uuid = "00000000-0000-0000-0000-000000000000"
    
    # 測試匯入 API
    try:
        data = {"process_id": invalid_uuid}
        response = requests.post(f"{API_BASE_URL}/api/import", json=data)
        
        print(f"📊 匯入 API 無效 ID 狀態碼：{response.status_code}")
        
        import_ok = response.status_code == 404
        if import_ok:
            print("✅ 匯入 API 正確回傳 404")
        else:
            print(f"❌ 匯入 API 錯誤處理異常：{response.text}")
            
    except Exception as e:
        print(f"❌ 匯入 API 無效 ID 測試失敗：{e}")
        import_ok = False
    
    # 測試匯出 API
    try:
        params = {"process_id": invalid_uuid}
        response = requests.get(f"{API_BASE_URL}/api/errors.csv", params=params)
        
        print(f"📊 匯出 API 無效 ID 狀態碼：{response.status_code}")
        
        export_ok = response.status_code == 404
        if export_ok:
            print("✅ 匯出 API 正確回傳 404")
        else:
            print(f"❌ 匯出 API 錯誤處理異常：{response.text}")
            
    except Exception as e:
        print(f"❌ 匯出 API 無效 ID 測試失敗：{e}")
        export_ok = False
    
    return import_ok and export_ok


def main():
    """主測試函數"""
    
    print("🚀 開始匯入和匯出 API 測試")
    print("時間：", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    # 檢查 API 連接
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code != 200:
            print("❌ API 伺服器未運行，請先啟動伺服器")
            return
    except Exception as e:
        print(f"❌ 無法連接到 API 伺服器：{e}")
        print("請確保伺服器已啟動在 http://localhost:8000")
        return
    
    # 1. 上傳檔案
    process_id = test_upload_and_get_process_id()
    if not process_id:
        print("❌ 無法獲取 process_id，測試終止")
        return
    
    # 2. 測試匯入
    import_test = test_import_api(process_id)
    
    # 3. 測試匯出
    export_test = test_export_errors_csv(process_id)
    
    # 4. 測試重複匯入
    repeat_import_test = test_import_already_imported(process_id)
    
    # 5. 測試無效 ID
    invalid_id_test = test_invalid_process_id_apis()
    
    # 總結
    print("\n" + "=" * 60)
    print("📋 測試結果總結：")
    print(f"   - 資料匯入：{'✅ 成功' if import_test else '❌ 失敗'}")
    print(f"   - 錯誤匯出：{'✅ 成功' if export_test else '❌ 失敗'}")
    print(f"   - 重複匯入檢查：{'✅ 成功' if repeat_import_test else '❌ 失敗'}")
    print(f"   - 無效 ID 處理：{'✅ 成功' if invalid_id_test else '❌ 失敗'}")
    
    if all([import_test, export_test, repeat_import_test, invalid_id_test]):
        print("\n🎊 所有測試通過！匯入和匯出 API 運作正常。")
        print(f"🌐 API 文檔：http://localhost:8000/docs")
        print(f"🔗 測試用的 Process ID：{process_id}")
    else:
        print("\n⚠️  部分測試失敗，請檢查 API 實作。")


if __name__ == "__main__":
    main()