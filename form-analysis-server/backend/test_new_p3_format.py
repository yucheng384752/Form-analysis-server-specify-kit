"""
測試新格式 P3 檔案的驗證和解析

新格式 P3 檔案特徵：
- 沒有 P3_No. 欄位
- 有 "lot no" 欄位（批號）
- 有 "Machine NO" 欄位（機台號碼）
- 有 "Mold NO" 欄位（模具編號）
- 有 "E Value" 欄位（非 "E_Value"）
"""

import sys
import os
import pandas as pd

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(__file__))

from app.services.csv_field_mapper import CSVFieldMapper, CSVType
from app.services.validation import FileValidationService


def test_new_p3_format_detection():
    """測試新格式 P3 檔案類型檢測"""
    print("\n=== 測試 1: 新格式 P3 檔案類型檢測 ===")
    
    mapper = CSVFieldMapper()
    
    # 新格式 P3 檔案的欄位
    new_p3_columns = [
        'year-month-day', 'Specification', 'Bottom Tape', 'Machine NO', 
        'Mold NO', 'paste iron temp', 'blow iron temp', 'first A size', 
        'last A size', 'first B size', 'last B size', 'lot no', 'E Value', 
        '10PO', 'Burr', 'Shift', 'Iron', 'Mold', 'Rubber Wheel', 'glue', 
        'lot', 'Adjustment Record', 'Finish', 'operator'
    ]
    
    filename = "P3_0902_P24.csv"
    detected_type = mapper.detect_csv_type(filename, new_p3_columns)
    
    print(f"檔案名稱: {filename}")
    print(f"欄位數量: {len(new_p3_columns)}")
    print(f"特徵欄位: Machine NO, Mold NO, E Value, Burr, Finish")
    print(f"偵測結果: {detected_type}")
    
    assert detected_type == CSVType.P3, f"檢測失敗！預期 P3，實際 {detected_type}"
    print("✓ 新格式 P3 檔案類型檢測成功")


def test_new_p3_format_field_extraction():
    """測試新格式 P3 檔案欄位提取"""
    print("\n=== 測試 2: 新格式 P3 檔案欄位提取 ===")
    
    mapper = CSVFieldMapper()
    
    # 模擬新格式 P3 CSV 資料
    row_data = {
        'year-month-day': '114年09月02日',
        'Specification': 'PE 32',
        'Bottom Tape': 'M250523-06-0159',
        'Machine NO': 'P24',
        'Mold NO': '238-2',
        'lot no': '2507173_02',  # 批號欄位
        'E Value': 990,
        'Burr': 1,
        'Finish': 1,
        'operator': 'anna'
    }
    
    row = pd.Series(row_data)
    filename = "P3_0902_P24.csv"
    
    result = mapper.extract_from_csv_row(row, CSVType.P3, filename)
    
    print(f"提取結果:")
    print(f"  machine_no: {result.get('machine_no')}")
    print(f"  mold_no: {result.get('mold_no')}")
    
    assert result.get('machine_no') == 'P24', f"machine_no 提取錯誤，實際：{result.get('machine_no')}"
    assert result.get('mold_no') == '238-2', f"mold_no 提取錯誤，實際：{result.get('mold_no')}"
    
    print("✓ 新格式 P3 檔案欄位提取成功")


def test_new_p3_format_validation():
    """測試新格式 P3 檔案驗證（含 7+2+2 批號格式）"""
    print("\n=== 測試 3: 新格式 P3 檔案驗證（彈性批號處理）===")
    
    # 建立測試 CSV 檔案，包含 7+2+2 格式的批號
    df = pd.DataFrame([
        {
            'year-month-day': '114年09月02日',
            'Specification': 'PE 32',
            'Bottom Tape': 'M250523-06-0159',
            'Machine NO': 'P24',
            'Mold NO': '238-2',
            'lot no': '2507173_02_17',  # 7+2+2 格式（應該被正規化為 2507173_02）
            'E Value': 990,
            'Burr': 1,
            'Finish': 1,
            'operator': 'anna'
        },
        {
            'year-month-day': '114年09月02日',
            'Specification': 'PE 32',
            'Bottom Tape': 'M250523-06-0159',
            'Machine NO': 'P24',
            'Mold NO': '238-2',
            'lot no': '2507173_02_18',  # 7+2+2 格式（應該被正規化為 2507173_02）
            'E Value': 990,
            'Burr': 1,
            'Finish': 1,
            'operator': 'anna'
        },
        {
            'year-month-day': '114年09月02日',
            'Specification': 'PE 32',
            'Bottom Tape': 'M250523-06-0159',
            'Machine NO': 'P24',
            'Mold NO': '238-2',
            'lot no': '2507173_02',  # 標準 7+2 格式（應該直接通過）
            'E Value': 990,
            'Burr': 1,
            'Finish': 1,
            'operator': 'anna'
        }
    ])
    
    # 轉換為 CSV bytes
    csv_content = df.to_csv(index=False).encode('utf-8')
    
    # 驗證檔案
    validator = FileValidationService()
    filename = "P3_0902_P24.csv"
    
    try:
        result = validator.validate_file(csv_content, filename)
        print(f"驗證結果:")
        print(f"  總行數: {result['total_rows']}")
        print(f"  有效行數: {result['valid_rows']}")
        print(f"  無效行數: {result['invalid_rows']}")
        print(f"  錯誤數: {len(result['errors'])}")
        
        if result['errors']:
            print(f"  錯誤詳情:")
            for error in result['errors'][:5]:  # 只顯示前5個錯誤
                print(f"    - Row {error['row_index']}: {error['field']} - {error['message']}")
        
        # 測試批號正規化
        print(f"\n  批號正規化測試:")
        test_lots = ['2507173_02_17', '2507173_02_18', '2507173_02']
        for lot in test_lots:
            normalized = validator.normalize_lot_no(lot)
            print(f"    {lot} → {normalized}")
        
        assert result['invalid_rows'] == 0, f"驗證失敗！發現 {result['invalid_rows']} 行錯誤"
        print("✓ 新格式 P3 檔案驗證成功（支援 7+2 和 7+2+2 格式）")
        
    except Exception as e:
        print(f"✗ 驗證失敗：{str(e)}")
        raise


def test_old_p3_format_still_works():
    """測試舊格式 P3 檔案仍然可用"""
    print("\n=== 測試 4: 舊格式 P3 檔案相容性 ===")
    
    # 舊格式 P3 檔案的欄位
    old_p3_columns = ['P3_No.', 'E_Value', 'Burr', 'Finish']
    
    mapper = CSVFieldMapper()
    filename = "P3_2411012_04.csv"
    detected_type = mapper.detect_csv_type(filename, old_p3_columns)
    
    print(f"檔案名稱: {filename}")
    print(f"欄位: {old_p3_columns}")
    print(f"偵測結果: {detected_type}")
    
    assert detected_type == CSVType.P3, f"檢測失敗！預期 P3，實際 {detected_type}"
    print("✓ 舊格式 P3 檔案仍然可被正確檢測")


if __name__ == "__main__":
    print("=" * 60)
    print("新格式 P3 檔案測試")
    print("=" * 60)
    
    try:
        test_new_p3_format_detection()
        test_new_p3_format_field_extraction()
        test_new_p3_format_validation()
        test_old_p3_format_still_works()
        
        print("\n" + "=" * 60)
        print("✓ 所有測試通過！")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"✗ 測試失敗：{str(e)}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)
