"""
簡單驗證腳本 - 測試新功能

不需要 pytest，直接執行驗證
"""

import sys
import os

# 添加專案路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_constants():
    """測試常數配置"""
    print("=" * 60)
    print("測試 1: 常數配置 (constants.py)")
    print("=" * 60)
    
    from app.config.constants import (
        VALID_MATERIALS,
        VALID_SLITTING_MACHINES,
        SLITTING_MACHINE_DISPLAY_NAMES,
        get_material_list,
        get_slitting_machine_list,
        get_slitting_machines_with_display_names,
        get_slitting_machine_display_name
    )
    
    # 測試材料清單
    assert VALID_MATERIALS == ["H2", "H5", "H8"], "材料清單不正確"
    print("✓ 材料清單正確:", VALID_MATERIALS)
    
    # 測試分條機清單
    assert VALID_SLITTING_MACHINES == [1, 2], "分條機清單不正確"
    print("✓ 分條機清單正確:", VALID_SLITTING_MACHINES)
    
    # 測試顯示名稱
    assert SLITTING_MACHINE_DISPLAY_NAMES[1] == "分1Points 1", "分條機1顯示名稱不正確"
    assert SLITTING_MACHINE_DISPLAY_NAMES[2] == "分2Points 2", "分條機2顯示名稱不正確"
    print("✓ 分條機顯示名稱正確:", SLITTING_MACHINE_DISPLAY_NAMES)
    
    # 測試函數
    materials = get_material_list()
    assert materials == ["H2", "H5", "H8"], "get_material_list() 返回值不正確"
    print("✓ get_material_list() 正確")
    
    machines = get_slitting_machines_with_display_names()
    assert len(machines) == 2, "分條機數量不正確"
    assert machines[0]['number'] == 1, "分條機1資訊不正確"
    print("✓ get_slitting_machines_with_display_names() 正確")
    
    display_name = get_slitting_machine_display_name(1)
    assert display_name == "分1Points 1", "分條機1顯示名稱不正確"
    print("✓ get_slitting_machine_display_name() 正確")
    
    print("\n常數配置測試通過!\n")


def test_validation():
    """測試驗證服務"""
    print("=" * 60)
    print("測試 2: 驗證服務 (validation.py)")
    print("=" * 60)
    
    from app.services.validation import FileValidationService
    import pandas as pd
    
    service = FileValidationService()
    
    # 測試 lot_no 正規化
    result = service.normalize_lot_no("2507173_02_17")
    assert result == "2507173-02", f"lot_no 正規化失敗: {result}"
    print(f"✓ normalize_lot_no('2507173_02_17') = '{result}'")
    
    result = service.normalize_lot_no("2507173_2_17")
    assert result == "2507173-02", f"lot_no 補零失敗: {result}"
    print(f"✓ normalize_lot_no('2507173_2_17') = '{result}' (補零)")
    
    # 測試 source_winder 提取
    result = service.extract_source_winder("2507173_02_17")
    assert result == 17, f"source_winder 提取失敗: {result}"
    print(f"✓ extract_source_winder('2507173_02_17') = {result}")
    
    result = service.extract_source_winder("2507173_02_5")
    assert result == 5, f"source_winder 提取失敗: {result}"
    print(f"✓ extract_source_winder('2507173_02_5') = {result}")
    
    # 測試材料代號驗證
    service.reset_counters()
    assert service.validate_material_code("H2", 0) is True
    assert service.validate_material_code("H5", 0) is True
    assert service.validate_material_code("H8", 0) is True
    print("✓ 有效材料代號驗證通過: H2, H5, H8")
    
    service.reset_counters()
    assert service.validate_material_code("H1", 0) is False
    assert len(service.errors) == 1
    print(f"✓ 無效材料代號驗證通過: H1 被拒絕")
    
    # 測試分條機編號驗證
    service.reset_counters()
    assert service.validate_slitting_machine_number(1, 0) is True
    assert service.validate_slitting_machine_number(2, 0) is True
    print("✓ 有效分條機編號驗證通過: 1, 2")
    
    service.reset_counters()
    assert service.validate_slitting_machine_number(3, 0) is False
    assert len(service.errors) == 1
    print(f"✓ 無效分條機編號驗證通過: 3 被拒絕")
    
    print("\n驗證服務測試通過!\n")


def test_csv_mapper():
    """測試 CSV 欄位映射器"""
    print("=" * 60)
    print("測試 3: CSV 欄位映射器 (csv_field_mapper.py)")
    print("=" * 60)
    
    from app.services.csv_field_mapper import CSVFieldMapper, CSVType
    import pandas as pd
    
    mapper = CSVFieldMapper()
    
    # 測試類型偵測
    csv_type = mapper.detect_csv_type("P1_2503033_01.csv", [])
    assert csv_type == CSVType.P1, f"P1 類型偵測失敗: {csv_type}"
    print(f"✓ 偵測 P1 檔案類型: 'P1_2503033_01.csv' → {csv_type}")
    
    csv_type = mapper.detect_csv_type("P2_2507173_02.csv", [])
    assert csv_type == CSVType.P2, f"P2 類型偵測失敗: {csv_type}"
    print(f"✓ 偵測 P2 檔案類型: 'P2_2507173_02.csv' → {csv_type}")
    
    csv_type = mapper.detect_csv_type("P3_0902_P24.csv", [])
    assert csv_type == CSVType.P3, f"P3 類型偵測失敗: {csv_type}"
    print(f"✓ 偵測 P3 檔案類型: 'P3_0902_P24.csv' → {csv_type}")
    
    # 測試根據欄位偵測
    columns = ["P3_No.", "E_Value", "Burr", "Finish"]
    csv_type = mapper.detect_csv_type("unknown.csv", columns)
    assert csv_type == CSVType.P3, f"根據欄位偵測 P3 失敗: {csv_type}"
    print(f"✓ 根據欄位偵測 P3: {columns[:2]}... → {csv_type}")
    
    # 測試 P3_No. 解析
    result = mapper._parse_p3_no("2411012_04_34_301")
    assert result['source_winder'] == 34, f"P3_No. 解析失敗: {result}"
    assert result['production_lot'] == 301, f"P3_No. 解析失敗: {result}"
    print(f"✓ 解析 P3_No. '2411012_04_34_301': source_winder={result['source_winder']}, production_lot={result['production_lot']}")
    
    # 測試機台編號提取
    machine = mapper._extract_machine_from_filename("P3_0902_P24.csv")
    assert machine == "P24", f"機台編號提取失敗: {machine}"
    print(f"✓ 從檔名提取機台編號: 'P3_0902_P24.csv' → {machine}")
    
    # 測試 P2 行提取
    row = pd.Series({
        "Material": "H8",
        "Slitting Machine": "1",
        "Winder": "15"
    })
    result = mapper.extract_from_csv_row(row, CSVType.P2, "P2_test.csv")
    assert result['material_code'] == "H8", f"P2 material_code 提取失敗: {result}"
    assert result['slitting_machine_number'] == 1, f"P2 slitting_machine 提取失敗: {result}"
    assert result['winder_number'] == 15, f"P2 winder 提取失敗: {result}"
    print(f"✓ P2 行提取: material={result['material_code']}, machine={result['slitting_machine_number']}, winder={result['winder_number']}")
    
    # 測試完整映射
    df = pd.DataFrame({
        "P3_No.": ["2411012_04_17_301", "2411012_04_18_302"],
        "E_Value": [990, 991],
        "Finish": [0, 1]
    })
    
    results = mapper.map_csv_to_record_fields(df, "P3_0902_P24.csv")
    assert len(results) == 2, f"映射結果數量不正確: {len(results)}"
    assert results[0]['source_winder'] == 17, f"第1行 source_winder 不正確: {results[0]}"
    assert results[0]['machine_no'] == "P24", f"第1行 machine_no 不正確: {results[0]}"
    assert 'additional_data' in results[0], "缺少 additional_data"
    print(f"✓ 完整映射測試: 2 行資料 → {len(results)} 筆結果")
    print(f"  - 第1行: source_winder={results[0]['source_winder']}, machine_no={results[0]['machine_no']}")
    
    print("\nCSV 欄位映射器測試通過!\n")


def test_record_model():
    """測試 Record 模型新欄位"""
    print("=" * 60)
    print("測試 4: Record 模型新欄位")
    print("=" * 60)
    
    from app.models.record import Record
    
    # 檢查新欄位是否存在
    new_fields = [
        'material_code',
        'slitting_machine_number',
        'winder_number',
        'machine_no',
        'mold_no',
        'production_lot',
        'source_winder',
        'product_id'
    ]
    
    for field in new_fields:
        assert hasattr(Record, field), f"Record 模型缺少欄位: {field}"
        print(f"✓ Record.{field} 存在")
    
    print("\nRecord 模型欄位測試通過!\n")


def main():
    """執行所有測試"""
    print("\n" + "=" * 60)
    print("開始驗證新功能")
    print("=" * 60 + "\n")
    
    try:
        test_constants()
        test_validation()
        test_csv_mapper()
        test_record_model()
        
        print("=" * 60)
        print("🎉 所有測試通過！")
        print("=" * 60)
        print("\n測試摘要:")
        print("1. 常數配置 (constants.py)")
        print("2. 驗證服務 (validation.py)")
        print("3. CSV 欄位映射器 (csv_field_mapper.py)")
        print("4. Record 模型新欄位")
        print("\n")
        
        return 0
        
    except AssertionError as e:
        print(f"\n測試失敗: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n執行錯誤: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
