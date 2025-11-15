"""
簡化版整合測試：完整檔案處理流程測試
不依賴 pytest，可直接執行
測試範圍：/api/upload → /api/validate → /api/import
"""

import asyncio
import tempfile
import os
import sys
import uuid
from pathlib import Path

# 將專案根目錄加入路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from httpx import AsyncClient
    from app.main import app
except ImportError as e:
    print(f" 缺少必要模組：{e}")
    print("請確保已安裝 FastAPI 和相關套件")
    sys.exit(1)

# 測試用的 CSV 資料（5列，其中2列有錯誤）
TEST_CSV_CONTENT = """product_name,lot_no,quantity,expiry_date,supplier
有效產品A,1234567_01,100,2024-12-31,供應商A
無效產品B,,50,2024-11-30,供應商B
有效產品C,2345678_02,200,2024-10-15,供應商C
無效產品D,INVALID,75,INVALID_DATE,供應商D
有效產品E,3456789_03,150,2024-09-20,供應商E"""

class SimpleIntegrationTest:
    """簡化的整合測試類別"""
    
    def __init__(self):
        self.client = None
        self.test_results = {}
    
    async def setup(self):
        """設置測試環境"""
        # 初始化資料庫
        try:
            from app.core.database import init_db
            await init_db()
            print(" 資料庫初始化完成")
        except Exception as e:
            print(f"  資料庫初始化警告：{e}")
        
        # 設置 HTTP 客戶端
        from httpx import ASGITransport
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://test")
        print(" 測試環境設置完成")
    
    async def cleanup(self):
        """清理測試環境"""
        if self.client:
            await self.client.aclose()
        print(" 測試環境清理完成")
    
    async def assert_response(self, response, expected_status, step_name):
        """驗證 API 回應"""
        if response.status_code != expected_status:
            print(f" {step_name} 失敗：期望狀態碼 {expected_status}，實際 {response.status_code}")
            print(f"   回應內容：{response.text}")
            return False
        
        print(f" {step_name} 成功：狀態碼 {response.status_code}")
        return True
    
    async def test_upload_file(self, csv_file_path):
        """步驟 1：測試檔案上傳"""
        print("\n📤 步驟 1：測試檔案上傳")
        
        with open(csv_file_path, 'rb') as f:
            files = {"file": ("test_data.csv", f, "text/csv")}
            response = await self.client.post("/api/upload", files=files)
        
        if not await self.assert_response(response, 200, "檔案上傳"):
            return None
        
        data = response.json()
        if "process_id" not in data:
            print(" 回應中缺少 process_id")
            return None
        
        process_id = data["process_id"]
        print(f"   Process ID: {process_id}")
        print(f"   訊息: {data.get('message', '無')}")
        
        # 等待驗證完成
        await asyncio.sleep(0.1)
        
        self.test_results['upload'] = data
        return process_id
    
    async def test_check_status(self, process_id):
        """步驟 2：測試狀態查詢"""
        print(f"\n 步驟 2：查詢工作狀態 {process_id}")
        
        response = await self.client.get(f"/api/upload/{process_id}/status")
        
        if not await self.assert_response(response, 200, "狀態查詢"):
            return None
        
        data = response.json()
        expected_fields = ["status", "total_rows", "error_count", "valid_count"]
        
        for field in expected_fields:
            if field not in data:
                print(f" 回應中缺少欄位：{field}")
                return None
        
        print(f"   狀態: {data['status']}")
        print(f"   總列數: {data['total_rows']}")
        print(f"   錯誤數: {data['error_count']}")
        print(f"   有效數: {data['valid_count']}")
        
        # 驗證預期結果
        if data['total_rows'] != 5:
            print(f" 總列數錯誤：期望 5，實際 {data['total_rows']}")
            return None
        
        if data['error_count'] != 2:
            print(f" 錯誤數錯誤：期望 2，實際 {data['error_count']}")
            return None
        
        if data['valid_count'] != 3:
            print(f" 有效數錯誤：期望 3，實際 {data['valid_count']}")
            return None
        
        self.test_results['status'] = data
        return data
    
    async def test_validate_results(self, process_id):
        """步驟 3：測試驗證結果查詢"""
        print(f"\n 步驟 3：查詢驗證結果 {process_id}")
        
        response = await self.client.get(
            f"/api/validate?process_id={process_id}&page=1&page_size=10"
        )
        
        if not await self.assert_response(response, 200, "驗證結果查詢"):
            return None
        
        data = response.json()
        required_sections = ["errors", "pagination", "summary"]
        
        for section in required_sections:
            if section not in data:
                print(f" 回應中缺少區塊：{section}")
                return None
        
        errors = data["errors"]
        pagination = data["pagination"]
        summary = data["summary"]
        
        print(f"   錯誤數量: {len(errors)}")
        print(f"   分頁資訊: 第 {pagination['current_page']}/{pagination['total_pages']} 頁")
        print(f"   摘要: {summary['error_count']} 錯誤，{summary['valid_count']} 有效")
        
        # 驗證錯誤數量
        if len(errors) != 2:
            print(f" 錯誤數量錯誤：期望 2，實際 {len(errors)}")
            return None
        
        # 顯示錯誤詳情
        for i, error in enumerate(errors, 1):
            print(f"   錯誤 {i}: 列 {error['row_index']} - {error['field']} - {error['message']}")
        
        self.test_results['validate'] = data
        return data
    
    async def test_export_csv(self, process_id):
        """步驟 4：測試錯誤 CSV 匯出"""
        print(f"\n 步驟 4：匯出錯誤 CSV {process_id}")
        
        response = await self.client.get(f"/api/errors.csv?process_id={process_id}")
        
        if not await self.assert_response(response, 200, "CSV 匯出"):
            return None
        
        # 檢查標頭
        content_type = response.headers.get("content-type", "")
        if "text/csv" not in content_type:
            print(f" Content-Type 錯誤：期望包含 text/csv，實際 {content_type}")
            return None
        
        # 檢查 CSV 內容
        csv_content = response.content.decode('utf-8-sig')
        csv_lines = csv_content.strip().split('\n')
        
        print(f"   CSV 列數: {len(csv_lines)}")
        print(f"   檔案大小: {len(csv_content)} 字元")
        
        if len(csv_lines) < 3:  # 標頭 + 至少 2 個錯誤
            print(f" CSV 內容不足：期望至少 3 列，實際 {len(csv_lines)}")
            return None
        
        # 檢查標頭
        expected_header = "row_index,field,error_code,message"
        if csv_lines[0] != expected_header:
            print(f" CSV 標頭錯誤：期望 {expected_header}")
            print(f"   實際: {csv_lines[0]}")
            return None
        
        print(f"   CSV 標頭正確: {csv_lines[0]}")
        print(f"   範例錯誤: {csv_lines[1]}")
        
        self.test_results['csv'] = {"content": csv_content, "lines": len(csv_lines)}
        return csv_content
    
    async def test_import_data(self, process_id):
        """步驟 5：測試資料匯入"""
        print(f"\n 步驟 5：匯入有效資料 {process_id}")
        
        response = await self.client.post(
            "/api/import",
            json={"process_id": process_id}
        )
        
        if not await self.assert_response(response, 200, "資料匯入"):
            return None
        
        data = response.json()
        required_fields = ["imported_rows", "skipped_rows", "elapsed_ms", "message"]
        
        for field in required_fields:
            if field not in data:
                print(f" 回應中缺少欄位：{field}")
                return None
        
        print(f"   匯入列數: {data['imported_rows']}")
        print(f"   跳過列數: {data['skipped_rows']}")
        print(f"   處理時間: {data['elapsed_ms']} ms")
        print(f"   訊息: {data['message']}")
        
        # 驗證結果
        if data['imported_rows'] != 3:
            print(f" 匯入列數錯誤：期望 3，實際 {data['imported_rows']}")
            return None
        
        if data['skipped_rows'] != 2:
            print(f" 跳過列數錯誤：期望 2，實際 {data['skipped_rows']}")
            return None
        
        self.test_results['import'] = data
        return data
    
    async def test_final_status(self, process_id):
        """步驟 6：測試最終狀態"""
        print(f"\n 步驟 6：驗證最終狀態 {process_id}")
        
        response = await self.client.get(f"/api/upload/{process_id}/status")
        
        if not await self.assert_response(response, 200, "最終狀態查詢"):
            return None
        
        data = response.json()
        
        if data['status'] != "IMPORTED":
            print(f" 最終狀態錯誤：期望 IMPORTED，實際 {data['status']}")
            return None
        
        print(f"   最終狀態: {data['status']}")
        
        self.test_results['final_status'] = data
        return data
    
    async def test_duplicate_import(self, process_id):
        """步驟 7：測試防重複匯入"""
        print(f"\n🚫 步驟 7：測試防重複匯入 {process_id}")
        
        response = await self.client.post(
            "/api/import",
            json={"process_id": process_id}
        )
        
        if not await self.assert_response(response, 400, "防重複匯入"):
            return None
        
        data = response.json()
        
        if "detail" not in data:
            print(" 錯誤回應格式不正確")
            return None
        
        print(f"   錯誤訊息: {data['detail']}")
        
        self.test_results['duplicate_import'] = data
        return data
    
    async def test_error_handling(self):
        """測試錯誤處理"""
        print(f"\n🧪 測試錯誤處理")
        
        fake_uuid = str(uuid.uuid4())
        
        # 測試不存在的驗證結果
        response = await self.client.get(f"/api/validate?process_id={fake_uuid}")
        if not await self.assert_response(response, 404, "查詢不存在的驗證結果"):
            return None
        
        # 測試不存在的匯入
        response = await self.client.post(
            "/api/import",
            json={"process_id": fake_uuid}
        )
        if not await self.assert_response(response, 404, "匯入不存在的工作"):
            return None
        
        # 測試不存在的 CSV 匯出
        response = await self.client.get(f"/api/errors.csv?process_id={fake_uuid}")
        if not await self.assert_response(response, 404, "匯出不存在的錯誤 CSV"):
            return None
        
        print(" 錯誤處理測試完成")
        return True

async def main():
    """主要測試函數"""
    print("🧪 開始完整流程整合測試")
    print("=" * 60)
    
    # 建立測試 CSV 檔案
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(TEST_CSV_CONTENT)
        csv_file_path = f.name
    
    test = SimpleIntegrationTest()
    success = True
    
    try:
        # 設置測試環境
        await test.setup()
        
        print(f"\n📝 測試資料：")
        print(f"   CSV 檔案：{csv_file_path}")
        print(f"   資料列數：5 列（2 列錯誤，3 列有效）")
        
        # 執行完整流程測試
        process_id = await test.test_upload_file(csv_file_path)
        if not process_id:
            success = False
        
        if success:
            await test.test_check_status(process_id)
        
        if success:
            await test.test_validate_results(process_id)
        
        if success:
            await test.test_export_csv(process_id)
        
        if success:
            await test.test_import_data(process_id)
        
        if success:
            await test.test_final_status(process_id)
        
        if success:
            await test.test_duplicate_import(process_id)
        
        # 錯誤處理測試
        if success:
            await test.test_error_handling()
        
        # 顯示測試結果摘要
        if success:
            print("\n" + "=" * 60)
            print("🎉 整合測試完成！")
            print("\n 測試結果摘要：")
            
            if 'upload' in test.test_results:
                print(f"   上傳成功：Process ID {process_id}")
            
            if 'status' in test.test_results:
                status = test.test_results['status']
                print(f"   驗證完成：{status['total_rows']} 列，{status['error_count']} 錯誤")
            
            if 'import' in test.test_results:
                import_data = test.test_results['import']
                print(f"   匯入完成：{import_data['imported_rows']} 列成功")
            
            if 'csv' in test.test_results:
                csv_data = test.test_results['csv']
                print(f"   CSV 匯出：{csv_data['lines']} 列")
            
            print("\n 測試涵蓋範圍：")
            print("   • 檔案上傳 (POST /api/upload)")
            print("   • 狀態查詢 (GET /api/upload/{id}/status)")
            print("   • 驗證結果 (GET /api/validate)")
            print("   • 錯誤匯出 (GET /api/errors.csv)")
            print("   • 資料匯入 (POST /api/import)")
            print("   • 錯誤處理流程")
            print("   • 防重複匯入測試")
            
        else:
            print("\n 整合測試失敗")
            
    except Exception as e:
        print(f"\n 測試執行時發生錯誤：{e}")
        import traceback
        traceback.print_exc()
        success = False
        
    finally:
        # 清理
        await test.cleanup()
        try:
            os.unlink(csv_file_path)
        except FileNotFoundError:
            pass
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit_code = 0 if success else 1
    print(f"\n程式結束，退出代碼：{exit_code}")
    sys.exit(exit_code)