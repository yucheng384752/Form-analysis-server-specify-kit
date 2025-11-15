"""
整合測試執行腳本
快速執行完整流程測試
"""

import sys
import os
import asyncio
import subprocess
import tempfile
from pathlib import Path

# 將專案根目錄加入路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_test_data():
    """建立測試資料檔案"""
    test_csv_content = """product_name,lot_no,quantity,expiry_date,supplier
有效產品A,1234567_01,100,2024-12-31,供應商A
無效產品B,,50,2024-11-30,供應商B
有效產品C,2345678_02,200,2024-10-15,供應商C
無效產品D,INVALID,75,INVALID_DATE,供應商D
有效產品E,3456789_03,150,2024-09-20,供應商E"""
    
    # 建立測試資料目錄
    test_data_dir = project_root / "test_data"
    test_data_dir.mkdir(exist_ok=True)
    
    # 寫入測試 CSV
    test_csv_path = test_data_dir / "integration_test_data.csv"
    with open(test_csv_path, 'w', encoding='utf-8') as f:
        f.write(test_csv_content)
    
    print(f" 測試資料已建立：{test_csv_path}")
    return test_csv_path

def check_dependencies():
    """檢查必要套件"""
    required_packages = ['pytest', 'httpx', 'sqlalchemy', 'fastapi']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f" 缺少必要套件：{', '.join(missing_packages)}")
        print("請執行：pip install " + " ".join(missing_packages))
        return False
    
    print(" 所有必要套件已安裝")
    return True

def run_integration_test():
    """執行整合測試"""
    print("\n🧪 開始執行整合測試...")
    
    # 檢查相依性
    if not check_dependencies():
        return False
    
    # 建立測試資料
    test_csv_path = create_test_data()
    
    try:
        # 使用 pytest 執行測試
        cmd = [
            sys.executable, "-m", "pytest", 
            "test_integration_full_flow.py",
            "-v",  # 詳細輸出
            "-s",  # 不捕獲 stdout
            "--tb=short",  # 簡化錯誤訊息
            "-x"   # 第一個錯誤就停止
        ]
        
        print(f"執行命令：{' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=project_root, capture_output=False)
        
        if result.returncode == 0:
            print("\n🎉 整合測試執行成功！")
            return True
        else:
            print(f"\n 整合測試失敗，退出代碼：{result.returncode}")
            return False
            
    except Exception as e:
        print(f"\n 執行測試時發生錯誤：{e}")
        return False

def run_direct_test():
    """直接執行測試（不使用 pytest）"""
    print("\n🧪 直接執行整合測試...")
    
    try:
        from test_integration_full_flow import TestFullFlowIntegration, TEST_CSV_CONTENT
        from app.main import app
        from httpx import AsyncClient
        
        async def execute_test():
            test_instance = TestFullFlowIntegration()
            
            # 建立臨時 CSV 檔案
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
                f.write(TEST_CSV_CONTENT)
                temp_path = f.name
            
            try:
                async with AsyncClient(app=app, base_url="http://test") as client:
                    print("\n📤 開始完整流程測試...")
                    
                    # 執行完整流程測試
                    result = await test_instance.test_complete_workflow(client, temp_path)
                    
                    print(f"\n📋 測試結果摘要：")
                    print(f"Process ID: {result['process_id']}")
                    print(f"上傳狀態: 成功")
                    print(f"驗證結果: {result['validate_data']['summary']['error_count']} 個錯誤")
                    print(f"匯入資料: {result['import_data']['imported_rows']} 列成功")
                    print(f"跳過資料: {result['import_data']['skipped_rows']} 列")
                    print(f"處理時間: {result['import_data']['elapsed_ms']} ms")
                    
                    # 執行錯誤處理測試
                    print("\n🚫 測試錯誤處理...")
                    await test_instance.test_error_handling_workflow(client)
                    
                    # 執行分頁測試
                    print("\n 測試分頁功能...")
                    await test_instance.test_pagination_workflow(client, temp_path)
                    
                    print("\n🎊 所有測試完成！")
                    return True
                    
            finally:
                # 清理臨時檔案
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass
        
        # 執行非同步測試
        return asyncio.run(execute_test())
        
    except Exception as e:
        print(f"\n 直接執行測試時發生錯誤：{e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主要執行函數"""
    print("🚀 整合測試執行器")
    print("=" * 50)
    
    # 檢查是否有 pytest
    try:
        import pytest
        use_pytest = True
    except ImportError:
        print("  未安裝 pytest，將使用直接執行模式")
        use_pytest = False
    
    # 執行測試
    if use_pytest:
        success = run_integration_test()
    else:
        success = run_direct_test()
    
    if success:
        print("\n 整合測試完成")
        print("\n 測試涵蓋範圍：")
        print("   • 檔案上傳 (POST /api/upload)")
        print("   • 狀態查詢 (GET /api/upload/{id}/status)")
        print("   • 驗證結果 (GET /api/validate)")
        print("   • 錯誤匯出 (GET /api/errors.csv)")
        print("   • 資料匯入 (POST /api/import)")
        print("   • 錯誤處理流程")
        print("   • 分頁功能測試")
        print("   • 防重複匯入測試")
        
        print("\n🎯 測試場景：")
        print("   • CSV 檔案：5 列資料")
        print("   • 錯誤資料：2 列（空白欄位、格式錯誤）")
        print("   • 有效資料：3 列")
        print("   • 完整工作流程：上傳→驗證→匯入")
        
    else:
        print("\n 整合測試失敗")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)