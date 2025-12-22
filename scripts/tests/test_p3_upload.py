"""
測試 P3 檔案上傳 - 檢查批號驗證是否正常運作
"""
import requests
import os

# API 端點
BASE_URL = "http://localhost:18002"
UPLOAD_URL = f"{BASE_URL}/api/upload"

# 測試檔案路徑
TEST_FILE = r"C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P3_0902_P24 copy.csv"

def test_upload():
    """測試上傳 P3 檔案"""
    print("=" * 80)
    print("測試 P3 檔案上傳")
    print("=" * 80)
    
    if not os.path.exists(TEST_FILE):
        print(f"❌ 檔案不存在: {TEST_FILE}")
        return
    
    print(f"✓ 檔案路徑: {TEST_FILE}")
    
    # 準備上傳請求
    with open(TEST_FILE, 'rb') as f:
        files = {'file': (os.path.basename(TEST_FILE), f, 'text/csv')}
        
        print("\n發送上傳請求...")
        try:
            response = requests.post(UPLOAD_URL, files=files)
            
            print(f"\n狀態碼: {response.status_code}")
            print(f"回應內容:")
            print("-" * 80)
            
            # 解析 JSON 回應
            try:
                data = response.json()
                
                # 漂亮印出 JSON
                import json
                print(json.dumps(data, ensure_ascii=False, indent=2))
                
                # 檢查驗證結果
                if response.status_code == 200:
                    print("\n✅ 檔案上傳成功！")
                    
                    if 'validation_result' in data:
                        validation = data['validation_result']
                        print(f"\n驗證結果:")
                        print(f"  - 總行數: {validation.get('total_rows', 'N/A')}")
                        print(f"  - 有效行數: {validation.get('valid_rows', 'N/A')}")
                        print(f"  - 無效行數: {validation.get('invalid_rows', 'N/A')}")
                        print(f"  - 資料類型: {validation.get('data_type', 'N/A')}")
                        print(f"  - 批號: {validation.get('lot_no', 'N/A')}")
                        
                        if validation.get('errors'):
                            print(f"\n❌ 驗證錯誤:")
                            for error in validation['errors'][:10]:  # 只顯示前 10 個
                                print(f"  - 行 {error.get('row')}: {error.get('message')}")
                else:
                    print(f"\n❌ 上傳失敗!")
                    
                    if 'detail' in data:
                        print(f"\n錯誤詳情: {data['detail']}")
                    
                    if 'validation_result' in data:
                        validation = data['validation_result']
                        if validation.get('errors'):
                            print(f"\n驗證錯誤（前 20 個）:")
                            for i, error in enumerate(validation['errors'][:20], 1):
                                print(f"  {i}. 行 {error.get('row')}, 欄位 {error.get('field')}: {error.get('message')}")
                
            except ValueError:
                print(response.text)
                
        except requests.exceptions.ConnectionError:
            print("❌ 無法連接到後端服務，請確認 Docker 容器正在運行")
        except Exception as e:
            print(f"❌ 發生錯誤: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_upload()
