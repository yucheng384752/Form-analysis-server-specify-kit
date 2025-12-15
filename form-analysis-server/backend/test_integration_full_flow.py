"""
整合測試：完整檔案處理流程測試
測試範圍：/api/upload → /api/validate → /api/import
"""

import pytest
import asyncio
import tempfile
import os
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.database import get_async_session
from app.models import UploadJob, UploadError
from sqlalchemy import select
import uuid
import io

# 測試用的 CSV 資料（5列，其中2列有錯誤）
TEST_CSV_CONTENT = """product_name,lot_no,quantity,expiry_date,supplier
有效產品A,1234567_01,100,2024-12-31,供應商A
無效產品B,,50,2024-11-30,供應商B
有效產品C,2345678_02,200,2024-10-15,供應商C
無效產品D,INVALID,75,INVALID_DATE,供應商D
有效產品E,3456789_03,150,2024-09-20,供應商E"""

class TestFullFlowIntegration:
    """完整流程整合測試"""
    
    @pytest.fixture
    async def async_client(self):
        """建立測試客戶端"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    async def test_csv_file(self):
        """建立測試 CSV 檔案"""
        # 建立臨時檔案
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(TEST_CSV_CONTENT)
            temp_path = f.name
        
        yield temp_path
        
        # 清理臨時檔案
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
    
    async def test_complete_workflow(self, async_client: AsyncClient, test_csv_file: str):
        """
        測試完整工作流程：上傳 → 驗證 → 匯入
        
        測試場景：
        - CSV 包含 5 列資料
        - 其中 2 列有錯誤（空白 lot_no 和無效格式）
        - 3 列資料有效
        """
        print("\n開始完整流程整合測試...")
        
        # ========== 步驟 1：檔案上傳 ==========
        print("\n📤 步驟 1：上傳 CSV 檔案")
        
        with open(test_csv_file, 'rb') as f:
            files = {"file": ("test_data.csv", f, "text/csv")}
            upload_response = await async_client.post("/api/upload", files=files)
        
        # 驗證上傳回應
        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        
        assert "process_id" in upload_data
        assert "message" in upload_data
        process_id = upload_data["process_id"]
        
        print(f" 上傳成功，process_id: {process_id}")
        print(f"   回應訊息: {upload_data['message']}")
        
        # 等待驗證完成（模擬非同步處理）
        await asyncio.sleep(0.1)
        
        # ========== 步驟 2：查詢工作狀態 ==========
        print("\n 步驟 2：查詢工作狀態")
        
        status_response = await async_client.get(f"/api/upload/{process_id}/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        
        assert status_data["status"] == "VALIDATED"
        assert status_data["total_rows"] == 5
        assert status_data["error_count"] == 2
        assert status_data["valid_count"] == 3
        
        print(f" 工作狀態查詢成功")
        print(f"   狀態: {status_data['status']}")
        print(f"   總列數: {status_data['total_rows']}")
        print(f"   錯誤數: {status_data['error_count']}")
        print(f"   有效數: {status_data['valid_count']}")
        
        # ========== 步驟 3：查詢驗證結果 ==========
        print("\n 步驟 3：查詢驗證結果（分頁）")
        
        # 查詢第一頁錯誤
        validate_response = await async_client.get(
            f"/api/validate?process_id={process_id}&page=1&page_size=10"
        )
        assert validate_response.status_code == 200
        validate_data = validate_response.json()
        
        # 驗證回應結構
        assert "errors" in validate_data
        assert "pagination" in validate_data
        assert "summary" in validate_data
        
        # 驗證錯誤數量
        errors = validate_data["errors"]
        assert len(errors) == 2  # 應該有 2 個錯誤
        
        # 驗證分頁資訊
        pagination = validate_data["pagination"]
        assert pagination["total_items"] == 2
        assert pagination["total_pages"] == 1
        assert pagination["current_page"] == 1
        assert pagination["page_size"] == 10
        
        # 驗證摘要資訊
        summary = validate_data["summary"]
        assert summary["total_rows"] == 5
        assert summary["error_count"] == 2
        assert summary["valid_count"] == 3
        
        print(f" 驗證結果查詢成功")
        print(f"   錯誤數量: {len(errors)}")
        print(f"   分頁資訊: 第 {pagination['current_page']}/{pagination['total_pages']} 頁")
        
        # 驗證具體錯誤內容
        error_rows = [error["row_index"] for error in errors]
        expected_error_rows = [2, 4]  # 第 2 列和第 4 列有錯誤
        assert sorted(error_rows) == sorted(expected_error_rows)
        
        print(f"   錯誤列索引: {sorted(error_rows)}")
        
        # 檢查具體錯誤訊息
        for error in errors:
            print(f"   列 {error['row_index']}: {error['field']} - {error['message']}")
        
        # ========== 步驟 4：匯出錯誤 CSV ==========
        print("\n 步驟 4：匯出錯誤 CSV")
        
        csv_response = await async_client.get(f"/api/errors.csv?process_id={process_id}")
        assert csv_response.status_code == 200
        
        # 驗證 CSV 標頭
        assert csv_response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in csv_response.headers.get("content-disposition", "")
        
        # 驗證 CSV 內容
        csv_content = csv_response.content.decode('utf-8-sig')  # 移除 BOM
        csv_lines = csv_content.strip().split('\n')
        
        assert len(csv_lines) >= 3  # 標頭 + 2 個錯誤列
        assert csv_lines[0] == "row_index,field,error_code,message"
        
        print(f" 錯誤 CSV 匯出成功")
        print(f"   CSV 列數: {len(csv_lines)}")
        print(f"   檔案大小: {len(csv_content)} 字元")
        
        # ========== 步驟 5：匯入有效資料 ==========
        print("\n 步驟 5：匯入有效資料")
        
        import_response = await async_client.post(
            "/api/import",
            json={"process_id": process_id}
        )
        assert import_response.status_code == 200
        import_data = import_response.json()
        
        # 驗證匯入結果
        assert import_data["imported_rows"] == 3  # 3 列有效資料
        assert import_data["skipped_rows"] == 2   # 2 列錯誤資料
        assert "elapsed_ms" in import_data
        assert import_data["process_id"] == process_id
        
        print(f" 資料匯入成功")
        print(f"   匯入列數: {import_data['imported_rows']}")
        print(f"   跳過列數: {import_data['skipped_rows']}")
        print(f"   處理時間: {import_data['elapsed_ms']} ms")
        print(f"   回應訊息: {import_data['message']}")
        
        # ========== 步驟 6：驗證最終狀態 ==========
        print("\n 步驟 6：驗證最終狀態")
        
        final_status_response = await async_client.get(f"/api/upload/{process_id}/status")
        assert final_status_response.status_code == 200
        final_status_data = final_status_response.json()
        
        assert final_status_data["status"] == "IMPORTED"
        
        print(f" 最終狀態確認")
        print(f"   狀態: {final_status_data['status']}")
        
        # ========== 步驟 7：防重複匯入測試 ==========
        print("\n🚫 步驟 7：測試防重複匯入")
        
        duplicate_import_response = await async_client.post(
            "/api/import",
            json={"process_id": process_id}
        )
        assert duplicate_import_response.status_code == 400
        duplicate_error = duplicate_import_response.json()
        
        assert "already_imported" in duplicate_error["detail"]["error_code"].lower()
        
        print(f" 防重複匯入測試通過")
        print(f"   錯誤程式碼: {duplicate_error['detail']['error_code']}")
        
        print("\n 完整流程整合測試成功完成！")
        
        return {
            "process_id": process_id,
            "upload_data": upload_data,
            "status_data": final_status_data,
            "validate_data": validate_data,
            "import_data": import_data
        }
    
    async def test_error_handling_workflow(self, async_client: AsyncClient):
        """
        測試錯誤處理流程
        """
        print("\n測試錯誤處理流程...")
        
        # 測試不存在的 process_id
        fake_uuid = str(uuid.uuid4())
        
        # 1. 查詢不存在的驗證結果
        validate_response = await async_client.get(f"/api/validate?process_id={fake_uuid}")
        assert validate_response.status_code == 404
        
        # 2. 嘗試匯入不存在的工作
        import_response = await async_client.post(
            "/api/import",
            json={"process_id": fake_uuid}
        )
        assert import_response.status_code == 404
        
        # 3. 匯出不存在的錯誤 CSV
        csv_response = await async_client.get(f"/api/errors.csv?process_id={fake_uuid}")
        assert csv_response.status_code == 404
        
        print(" 錯誤處理流程測試通過")
    
    async def test_pagination_workflow(self, async_client: AsyncClient, test_csv_file: str):
        """
        測試分頁功能
        """
        print("\n測試分頁功能...")
        
        # 上傳檔案
        with open(test_csv_file, 'rb') as f:
            files = {"file": ("test_data.csv", f, "text/csv")}
            upload_response = await async_client.post("/api/upload", files=files)
        
        process_id = upload_response.json()["process_id"]
        await asyncio.sleep(0.1)  # 等待驗證完成
        
        # 測試小頁面大小的分頁
        page1_response = await async_client.get(
            f"/api/validate?process_id={process_id}&page=1&page_size=1"
        )
        assert page1_response.status_code == 200
        page1_data = page1_response.json()
        
        assert len(page1_data["errors"]) == 1
        assert page1_data["pagination"]["total_pages"] == 2
        assert page1_data["pagination"]["current_page"] == 1
        
        # 測試第二頁
        page2_response = await async_client.get(
            f"/api/validate?process_id={process_id}&page=2&page_size=1"
        )
        assert page2_response.status_code == 200
        page2_data = page2_response.json()
        
        assert len(page2_data["errors"]) == 1
        assert page2_data["pagination"]["current_page"] == 2
        
        # 確保兩頁的錯誤不重複
        page1_row = page1_data["errors"][0]["row_index"]
        page2_row = page2_data["errors"][0]["row_index"]
        assert page1_row != page2_row
        
        print(" 分頁功能測試通過")

if __name__ == "__main__":
    """直接執行測試"""
    import asyncio
    
    async def run_tests():
        test_instance = TestFullFlowIntegration()
        
        # 建立測試 CSV 檔案
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(TEST_CSV_CONTENT)
            temp_path = f.name
        
        try:
            async with AsyncClient(app=app, base_url="http://test") as client:
                # 執行完整流程測試
                result = await test_instance.test_complete_workflow(client, temp_path)
                print(f"\n 測試結果摘要:")
                print(f"Process ID: {result['process_id']}")
                print(f"匯入資料: {result['import_data']['imported_rows']} 列")
                print(f"跳過資料: {result['import_data']['skipped_rows']} 列")
                
                # 執行錯誤處理測試
                await test_instance.test_error_handling_workflow(client)
                
                # 執行分頁測試
                await test_instance.test_pagination_workflow(client, temp_path)
                
        finally:
            # 清理臨時檔案
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
        
        print("\n🎊 所有整合測試完成！")
    
    # 執行測試
    asyncio.run(run_tests())