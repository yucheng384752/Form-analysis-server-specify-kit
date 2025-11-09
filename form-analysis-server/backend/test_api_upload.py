"""
API 測試腳本

測試檔案上傳 API 端點的功能。
需要先啟動 FastAPI 伺服器。
"""

import asyncio
import aiohttp
import csv
import io
import sys
import os
from datetime import datetime

# API 基礎 URL
API_BASE_URL = "http://localhost:8000"


def create_valid_test_csv():
    """建立有效的測試 CSV 檔案"""
    
    test_data = [
        ["1234567_01", "測試產品A", "100", "2024-01-01"],
        ["2345678_02", "測試產品B", "200", "2024-01-02"],
        ["3456789_03", "測試產品C", "300", "2024-01-03"],
    ]
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 寫入標題
    writer.writerow(["lot_no", "product_name", "quantity", "production_date"])
    
    # 寫入資料
    for row in test_data:
        writer.writerow(row)
    
    csv_content = output.getvalue()
    output.close()
    
    return csv_content.encode('utf-8')


def create_invalid_test_csv():
    """建立包含錯誤的測試 CSV 檔案"""
    
    test_data = [
        ["1234567_01", "測試產品A", "100", "2024-01-01"],  # 有效
        ["123456_01", "測試產品B", "200", "2024-01-02"],   # 批號錯誤
        ["2345678_02", "測試產品C", "-50", "2024-01-03"],  # 數量負數
        ["3456789_03", "", "300", "2024/01/04"],           # 名稱空、日期格式錯
    ]
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["lot_no", "product_name", "quantity", "production_date"])
    
    for row in test_data:
        writer.writerow(row)
    
    csv_content = output.getvalue()
    output.close()
    
    return csv_content.encode('utf-8')


async def test_api_connection():
    """測試 API 連接"""
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/") as response:
                if response.status == 200:
                    print("✅ API 伺服器連接成功")
                    return True
                else:
                    print(f"❌ API 伺服器回應錯誤：{response.status}")
                    return False
    except Exception as e:
        print(f"❌ 無法連接到 API 伺服器：{e}")
        print("請確保 FastAPI 伺服器已啟動 (python -m uvicorn app.main:app --reload)")
        return False


async def test_valid_file_upload():
    """測試有效檔案上傳"""
    
    print("\n🧪 測試有效檔案上傳...")
    print("-" * 40)
    
    csv_content = create_valid_test_csv()
    
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('file', csv_content, filename='valid_test.csv', content_type='text/csv')
            
            async with session.post(f"{API_BASE_URL}/api/upload", data=data) as response:
                response_data = await response.json()
                
                print(f"📊 HTTP 狀態碼：{response.status}")
                
                if response.status == 200:
                    print("✅ 檔案上傳成功")
                    print(f"📝 回應：{response_data}")
                    
                    if 'process_id' in response_data:
                        return response_data['process_id']
                    else:
                        print("❌ 回應中沒有 process_id")
                        return None
                else:
                    print(f"❌ 上傳失敗：{response_data}")
                    return None
                    
    except Exception as e:
        print(f"❌ 上傳請求失敗：{e}")
        return None


async def test_invalid_file_upload():
    """測試無效檔案上傳"""
    
    print("\n🧪 測試包含錯誤的檔案上傳...")
    print("-" * 40)
    
    csv_content = create_invalid_test_csv()
    
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('file', csv_content, filename='invalid_test.csv', content_type='text/csv')
            
            async with session.post(f"{API_BASE_URL}/api/upload", data=data) as response:
                response_data = await response.json()
                
                print(f"📊 HTTP 狀態碼：{response.status}")
                
                if response.status == 400:
                    print("✅ 正確偵測到檔案驗證錯誤")
                    print(f"📝 錯誤詳情：{response_data}")
                    return True
                else:
                    print(f"❌ 未正確處理驗證錯誤：{response_data}")
                    return False
                    
    except Exception as e:
        print(f"❌ 上傳請求失敗：{e}")
        return False


async def test_upload_status(process_id):
    """測試上傳狀態查詢"""
    
    if not process_id:
        return False
        
    print(f"\n🧪 測試狀態查詢 (Process ID: {process_id})...")
    print("-" * 40)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/api/upload/{process_id}/status") as response:
                response_data = await response.json()
                
                print(f"📊 HTTP 狀態碼：{response.status}")
                
                if response.status == 200:
                    print("✅ 狀態查詢成功")
                    print(f"📝 狀態資訊：{response_data}")
                    return True
                else:
                    print(f"❌ 狀態查詢失敗：{response_data}")
                    return False
                    
    except Exception as e:
        print(f"❌ 狀態查詢請求失敗：{e}")
        return False


async def main():
    """主測試函數"""
    
    print("🚀 開始 API 測試")
    print("時間：", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("API 地址：", API_BASE_URL)
    
    # 測試 API 連接
    connection_ok = await test_api_connection()
    if not connection_ok:
        return
    
    # 測試有效檔案上傳
    process_id = await test_valid_file_upload()
    valid_upload_ok = process_id is not None
    
    # 測試無效檔案上傳
    invalid_upload_ok = await test_invalid_file_upload()
    
    # 測試狀態查詢
    status_ok = await test_upload_status(process_id)
    
    # 總結
    print("\n" + "=" * 50)
    print("📋 API 測試結果總結：")
    print(f"   - API 連接：{'✅ 成功' if connection_ok else '❌ 失敗'}")
    print(f"   - 有效檔案上傳：{'✅ 成功' if valid_upload_ok else '❌ 失敗'}")
    print(f"   - 無效檔案處理：{'✅ 成功' if invalid_upload_ok else '❌ 失敗'}")
    print(f"   - 狀態查詢：{'✅ 成功' if status_ok else '❌ 失敗'}")
    
    if all([connection_ok, valid_upload_ok, invalid_upload_ok, status_ok]):
        print("\n🎊 所有 API 測試通過！")
    else:
        print("\n⚠️  部分 API 測試失敗，請檢查伺服器狀態。")


if __name__ == "__main__":
    asyncio.run(main())