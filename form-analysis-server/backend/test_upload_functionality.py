"""
測試檔案上傳功能

建立測試用的 CSV 檔案並驗證上傳功能。
"""

import asyncio
import csv
import io
import sys
import os
from datetime import date, datetime

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.validation import file_validation_service


def create_test_csv_content():
    """建立測試用的 CSV 內容"""
    
    # 準備測試資料：包含有效和無效的資料
    test_data = [
        # 有效資料
        ["1234567_01", "測試產品A", "100", "2024-01-01"],
        ["2345678_02", "測試產品B", "200", "2024-01-02"],
        ["3456789_03", "測試產品C", "300", "2024-01-03"],
        
        # 無效資料 - 批號格式錯誤
        ["123456_01", "測試產品D", "400", "2024-01-04"],  # 批號太短
        ["12345678_01", "測試產品E", "500", "2024-01-05"],  # 批號太長
        
        # 無效資料 - 數量錯誤
        ["4567890_04", "測試產品F", "-100", "2024-01-06"],  # 負數
        ["5678901_05", "測試產品G", "abc", "2024-01-07"],   # 非數字
        
        # 無效資料 - 日期錯誤
        ["6789012_06", "測試產品H", "600", "2024/01/08"],   # 錯誤格式
        ["7890123_07", "測試產品I", "700", "invalid-date"], # 無效日期
        
        # 無效資料 - 空值
        ["", "測試產品J", "800", "2024-01-10"],              # 空批號
        ["8901234_08", "", "900", "2024-01-11"],             # 空產品名稱
    ]
    
    # 建立 CSV 內容
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


async def test_file_validation():
    """測試檔案驗證功能"""
    
    print("🧪 開始測試檔案上傳驗證功能...")
    print("=" * 50)
    
    # 1. 建立測試 CSV 檔案
    csv_content = create_test_csv_content()
    print(f" 建立測試 CSV 檔案，大小：{len(csv_content)} 位元組")
    
    # 2. 執行檔案驗證
    try:
        result = file_validation_service.validate_file(csv_content, "test_data.csv")
        
        print(f" 檔案驗證完成")
        print(f" 統計結果：")
        print(f"   - 總行數：{result['total_rows']}")
        print(f"   - 有效行數：{result['valid_rows']}")
        print(f"   - 無效行數：{result['invalid_rows']}")
        
        # 3. 顯示錯誤樣本
        if result['sample_errors']:
            print(f"\n 錯誤樣本（前 {len(result['sample_errors'])} 筆）：")
            for i, error in enumerate(result['sample_errors'], 1):
                print(f"   {i}. 行 {error['row_index']}, 欄位 '{error['field']}': {error['message']}")
        else:
            print("\n 無驗證錯誤")
            
    except Exception as e:
        print(f" 驗證失敗：{e}")
        return False
    
    print("\n" + "=" * 50)
    print(" 測試完成！")
    return True


def create_invalid_columns_csv():
    """建立包含無效欄位的 CSV 內容"""
    
    # 缺少必要欄位，包含未知欄位
    test_data = [
        ["1234567_01", "測試產品A", "100", "unknown_data"],
    ]
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 寫入錯誤的標題（缺少 production_date，多了 extra_column）
    writer.writerow(["lot_no", "product_name", "quantity", "extra_column"])
    
    for row in test_data:
        writer.writerow(row)
    
    csv_content = output.getvalue()
    output.close()
    
    return csv_content.encode('utf-8')


async def test_column_validation():
    """測試欄位驗證功能"""
    
    print("\n🧪 測試欄位驗證功能...")
    print("=" * 50)
    
    # 測試缺少必要欄位的情況
    invalid_csv = create_invalid_columns_csv()
    
    try:
        result = file_validation_service.validate_file(invalid_csv, "invalid_columns.csv")
        print(" 應該要拋出驗證錯誤，但沒有")
        return False
    except Exception as e:
        print(f" 正確捕獲到欄位驗證錯誤：{e}")
        return True


async def main():
    """主測試函數"""
    
    print(" 開始檔案上傳功能測試")
    print("時間：", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # 測試正常檔案驗證
    test1_passed = await test_file_validation()
    
    # 測試欄位驗證
    test2_passed = await test_column_validation()
    
    print(f"\n 測試結果總結：")
    print(f"   - 檔案驗證測試：{' 通過' if test1_passed else ' 失敗'}")
    print(f"   - 欄位驗證測試：{' 通過' if test2_passed else ' 失敗'}")
    
    if test1_passed and test2_passed:
        print("\n🎊 所有測試通過！檔案上傳功能已準備就緒。")
    else:
        print("\n  部分測試失敗，請檢查程式碼。")


if __name__ == "__main__":
    asyncio.run(main())