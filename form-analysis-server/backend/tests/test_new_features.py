"""
測試新增功能：constants, validation, csv_field_mapper

測試範圍：
1. constants.py - 材料/分條機常數
2. validation.py - lot_no 正規化 + 常數驗證
3. csv_field_mapper.py - CSV 欄位映射器
"""

import pytest
import pandas as pd
from app.config.constants import (
    VALID_MATERIALS,
    VALID_SLITTING_MACHINES,
    SLITTING_MACHINE_DISPLAY_NAMES,
    get_material_list,
    get_slitting_machine_list,
    get_slitting_machines_with_display_names,
    get_slitting_machine_display_name
)
from app.services.validation import FileValidationService
from app.services.csv_field_mapper import CSVFieldMapper, CSVType


class TestConstants:
    """測試常數配置"""
    
    def test_valid_materials(self):
        """測試材料清單"""
        assert VALID_MATERIALS == ["H2", "H5", "H8"]
        assert len(VALID_MATERIALS) == 3
    
    def test_valid_slitting_machines(self):
        """測試分條機清單"""
        assert VALID_SLITTING_MACHINES == [1, 2]
        assert len(VALID_SLITTING_MACHINES) == 2
    
    def test_slitting_machine_display_names(self):
        """測試分條機顯示名稱"""
        assert SLITTING_MACHINE_DISPLAY_NAMES[1] == "分條1"
        assert SLITTING_MACHINE_DISPLAY_NAMES[2] == "分條2"
    
    def test_get_material_list(self):
        """測試取得材料清單"""
        materials = get_material_list()
        assert materials == ["H2", "H5", "H8"]
    
    def test_get_slitting_machine_list(self):
        """測試取得分條機清單"""
        machines = get_slitting_machine_list()
        assert machines == [1, 2]
    
    def test_get_slitting_machines_with_display_names(self):
        """測試取得分條機及顯示名稱"""
        machines = get_slitting_machines_with_display_names()
        assert len(machines) == 2
        assert machines[0] == {"number": 1, "display_name": "分條1"}
        assert machines[1] == {"number": 2, "display_name": "分條2"}
    
    def test_get_slitting_machine_display_name(self):
        """測試取得單一分條機顯示名稱"""
        assert get_slitting_machine_display_name(1) == "分條1"
        assert get_slitting_machine_display_name(2) == "分條2"
        assert get_slitting_machine_display_name(999) == "未知"


class TestValidationService:
    """測試驗證服務新功能"""
    
    @pytest.fixture
    def validation_service(self):
        """創建驗證服務實例"""
        return FileValidationService()
    
    def test_normalize_lot_no_standard(self, validation_service):
        """測試標準批號正規化"""
        # 標準格式：已經是兩位數
        result = validation_service.normalize_lot_no("2507173_02_17")
        assert result == "2507173-02"
    
    def test_normalize_lot_no_single_digit(self, validation_service):
        """測試單位數批號正規化"""
        # 單位數需要補零
        result = validation_service.normalize_lot_no("2507173_2_17")
        assert result == "2507173-02"
    
    def test_normalize_lot_no_without_winder(self, validation_service):
        """測試無收卷機編號的批號"""
        result = validation_service.normalize_lot_no("2507173_02")
        assert result == "2507173-02"
    
    def test_normalize_lot_no_empty(self, validation_service):
        """測試空批號"""
        result = validation_service.normalize_lot_no("")
        assert result == ""
    
    def test_normalize_lot_no_invalid(self, validation_service):
        """測試無效格式批號"""
        result = validation_service.normalize_lot_no("invalid")
        assert result == "invalid"  # 無法轉換時返回原值
    
    def test_extract_source_winder_standard(self, validation_service):
        """測試提取來源收卷機編號"""
        result = validation_service.extract_source_winder("2507173_02_17")
        assert result == 17
    
    def test_extract_source_winder_single_digit(self, validation_service):
        """測試單位數收卷機編號"""
        result = validation_service.extract_source_winder("2507173_02_5")
        assert result == 5
    
    def test_extract_source_winder_missing(self, validation_service):
        """測試缺少收卷機編號"""
        result = validation_service.extract_source_winder("2507173_02")
        assert result is None
    
    def test_extract_source_winder_empty(self, validation_service):
        """測試空字串"""
        result = validation_service.extract_source_winder("")
        assert result is None
    
    def test_validate_material_code_valid(self, validation_service):
        """測試有效材料代號"""
        assert validation_service.validate_material_code("H2", 0) is True
        assert validation_service.validate_material_code("H5", 0) is True
        assert validation_service.validate_material_code("H8", 0) is True
    
    def test_validate_material_code_invalid(self, validation_service):
        """測試無效材料代號"""
        validation_service.reset_counters()
        assert validation_service.validate_material_code("H1", 0) is False
        assert len(validation_service.errors) == 1
        assert "H1" in validation_service.errors[0]['message']
    
    def test_validate_material_code_case_insensitive(self, validation_service):
        """測試材料代號大小寫不敏感"""
        assert validation_service.validate_material_code("h2", 0) is True
        assert validation_service.validate_material_code("h5", 0) is True
    
    def test_validate_material_code_none(self, validation_service):
        """測試空材料代號（可選欄位）"""
        assert validation_service.validate_material_code(None, 0) is True
        assert validation_service.validate_material_code(pd.NA, 0) is True
    
    def test_validate_slitting_machine_valid(self, validation_service):
        """測試有效分條機編號"""
        assert validation_service.validate_slitting_machine_number(1, 0) is True
        assert validation_service.validate_slitting_machine_number(2, 0) is True
    
    def test_validate_slitting_machine_invalid(self, validation_service):
        """測試無效分條機編號"""
        validation_service.reset_counters()
        assert validation_service.validate_slitting_machine_number(3, 0) is False
        assert len(validation_service.errors) == 1
        assert "3" in validation_service.errors[0]['message']
    
    def test_validate_slitting_machine_non_integer(self, validation_service):
        """測試非整數分條機編號"""
        validation_service.reset_counters()
        assert validation_service.validate_slitting_machine_number("abc", 0) is False
        assert len(validation_service.errors) == 1
        assert "整數" in validation_service.errors[0]['message']
    
    def test_validate_slitting_machine_none(self, validation_service):
        """測試空分條機編號（可選欄位）"""
        assert validation_service.validate_slitting_machine_number(None, 0) is True
        assert validation_service.validate_slitting_machine_number(pd.NA, 0) is True


class TestCSVFieldMapper:
    """測試 CSV 欄位映射器"""
    
    @pytest.fixture
    def mapper(self):
        """創建映射器實例"""
        return CSVFieldMapper()
    
    def test_detect_csv_type_by_filename_p1(self, mapper):
        """測試根據檔案名稱偵測 P1"""
        result = mapper.detect_csv_type("P1_2503033_01.csv", [])
        assert result == CSVType.P1
    
    def test_detect_csv_type_by_filename_p2(self, mapper):
        """測試根據檔案名稱偵測 P2"""
        result = mapper.detect_csv_type("P2_2507173_02.csv", [])
        assert result == CSVType.P2
    
    def test_detect_csv_type_by_filename_p3(self, mapper):
        """測試根據檔案名稱偵測 P3"""
        result = mapper.detect_csv_type("P3_0902_P24.csv", [])
        assert result == CSVType.P3
    
    def test_detect_csv_type_by_columns_p3(self, mapper):
        """測試根據欄位偵測 P3"""
        columns = ["P3_No.", "E_Value", "Burr", "Finish"]
        result = mapper.detect_csv_type("unknown.csv", columns)
        assert result == CSVType.P3
    
    def test_detect_csv_type_by_columns_p2(self, mapper):
        """測試根據欄位偵測 P2"""
        columns = ["Sheet Width(mm)", "Thicknessss1(μm)", "Appearance", "Slitting Result"]
        result = mapper.detect_csv_type("unknown.csv", columns)
        assert result == CSVType.P2
    
    def test_detect_csv_type_by_columns_p1(self, mapper):
        """測試根據欄位偵測 P1"""
        columns = [
            "Actual Temp_C1(℃)", "Set Temp_C1(℃)", 
            "Line Speed(M/min)", "Screw Pressure(psi)", 
            "Extruder Speed(rpm)"
        ]
        result = mapper.detect_csv_type("unknown.csv", columns)
        assert result == CSVType.P1
    
    def test_parse_p3_no_standard(self, mapper):
        """測試解析標準 P3_No."""
        result = mapper._parse_p3_no("2411012_04_34_301")
        assert result['source_winder'] == 34
        assert result['production_lot'] == 301
    
    def test_parse_p3_no_single_digit_winder(self, mapper):
        """測試單位數收卷機編號"""
        result = mapper._parse_p3_no("2411012_04_5_302")
        assert result['source_winder'] == 5
        assert result['production_lot'] == 302
    
    def test_parse_p3_no_invalid(self, mapper):
        """測試無效 P3_No."""
        result = mapper._parse_p3_no("invalid")
        assert result == {}
    
    def test_extract_machine_from_filename(self, mapper):
        """測試從檔案名稱提取機台編號"""
        result = mapper._extract_machine_from_filename("P3_0902_P24.csv")
        assert result == "P24"
        
        result = mapper._extract_machine_from_filename("P3_0210_P02.csv")
        assert result == "P02"
    
    def test_extract_machine_from_filename_invalid(self, mapper):
        """測試無效檔案名稱"""
        result = mapper._extract_machine_from_filename("invalid.csv")
        assert result is None
    
    def test_extract_from_csv_row_p1(self, mapper):
        """測試 P1 行提取"""
        row = pd.Series({"Material": "H5", "other_field": "value"})
        result = mapper.extract_from_csv_row(row, CSVType.P1, "P1_test.csv")
        assert result['material_code'] == "H5"
    
    def test_extract_from_csv_row_p2(self, mapper):
        """測試 P2 行提取"""
        row = pd.Series({
            "Material": "H8",
            "Slitting Machine": "1",
            "Winder": "15"
        })
        result = mapper.extract_from_csv_row(row, CSVType.P2, "P2_test.csv")
        assert result['material_code'] == "H8"
        assert result['slitting_machine_number'] == 1
        assert result['winder_number'] == 15
    
    def test_extract_from_csv_row_p3(self, mapper):
        """測試 P3 行提取"""
        row = pd.Series({"P3_No.": "2411012_04_17_301"})
        result = mapper.extract_from_csv_row(row, CSVType.P3, "P3_0902_P24.csv")
        assert result['source_winder'] == 17
        assert result['production_lot'] == 301
        assert result['machine_no'] == "P24"
    
    def test_map_csv_to_record_fields(self, mapper):
        """測試完整映射流程"""
        df = pd.DataFrame({
            "P3_No.": ["2411012_04_17_301", "2411012_04_18_302"],
            "E_Value": [990, 991],
            "Finish": [0, 1]
        })
        
        results = mapper.map_csv_to_record_fields(df, "P3_0902_P24.csv")
        
        assert len(results) == 2
        assert results[0]['source_winder'] == 17
        assert results[0]['production_lot'] == 301
        assert results[0]['machine_no'] == "P24"
        assert 'additional_data' in results[0]
        assert results[0]['additional_data']['E_Value'] == 990


class TestRecordModelFields:
    """測試 Record 模型新增欄位（簡單檢查）"""
    
    def test_record_model_has_new_fields(self):
        """測試 Record 模型包含新欄位"""
        from app.models.record import Record
        
        # 檢查新欄位是否存在於模型中
        assert hasattr(Record, 'material_code')
        assert hasattr(Record, 'slitting_machine_number')
        assert hasattr(Record, 'winder_number')
        assert hasattr(Record, 'machine_no')
        assert hasattr(Record, 'mold_no')
        assert hasattr(Record, 'production_lot')
        assert hasattr(Record, 'source_winder')
        assert hasattr(Record, 'product_id')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
