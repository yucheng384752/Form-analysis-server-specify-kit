#!/usr/bin/env python3
"""測試 P3 檔案完整流程（上傳 + 匯入）"""

import requests
import json

def test_full_flow():
    file_path = r"C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P3_0902_P24 copy.csv"
    
    # Step 1: 上傳並驗證
    print("=" * 80)
    print("步驟 1: 上傳並驗證檔案")
    print("=" * 80)
    
    with open(file_path, 'rb') as f:
        files = {'file': ('P3_0902_P24.csv', f, 'text/csv')}
        response = requests.post("http://localhost:18002/api/upload", files=files, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ 上傳失敗: {response.text}")
        return
    
    upload_result = response.json()
    print(f"✅ 上傳成功!")
    print(json.dumps(upload_result, indent=2, ensure_ascii=False))
    
    process_id = upload_result['process_id']
    
    # Step 2: 匯入資料
    print("\n" + "=" * 80)
    print("步驟 2: 匯入驗證通過的資料")
    print("=" * 80)
    
    import_data = {"process_id": process_id}
    response = requests.post(
        "http://localhost:18002/api/import",
        json=import_data,
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ 匯入失敗: {response.text}")
        return
    
    import_result = response.json()
    print(f"✅ 匯入成功!")
    print(json.dumps(import_result, indent=2, ensure_ascii=False))
    
    # Step 3: 驗證資料庫
    print("\n" + "=" * 80)
    print("步驟 3: 查詢資料庫驗證")
    print("=" * 80)
    
    # 查詢剛匯入的批號
    response = requests.get(
        f"http://localhost:18002/api/records?lot_no=2507173_02&data_type=P3",
        timeout=30
    )
    
    if response.status_code == 200:
        records = response.json()
        print(f"\n✅ 找到 {len(records.get('items', []))} 筆記錄")
        for record in records.get('items', [])[:3]:  # 只顯示前 3 筆
            print(f"  - 批號: {record.get('lot_no')}, "
                  f"機台: {record.get('machine_no')}, "
                  f"模具: {record.get('mold_no')}")
    else:
        print(f"⚠️  查詢失敗: {response.status_code}")

if __name__ == "__main__":
    test_full_flow()
