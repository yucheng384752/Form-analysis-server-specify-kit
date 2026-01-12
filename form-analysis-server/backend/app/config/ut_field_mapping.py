"""
侑特 (UT) 資料欄位映射配置
支援 P1, P2, P3 及組合查詢（P1+P2+P3）
"""

from typing import Dict, Any

# ============ P1 欄位映射（原料/擠出） ============
P1_FIELD_MAPPING = {
    # 溫度相關（C1-C8）
    "Actual Temp_C1(℃)": "extras.temperature.actual.C1",
    "Actual Temp_C2(℃)": "extras.temperature.actual.C2",
    "Actual Temp_C3(℃)": "extras.temperature.actual.C3",
    "Actual Temp_C4(℃)": "extras.temperature.actual.C4",
    "Actual Temp_C5(℃)": "extras.temperature.actual.C5",
    "Actual Temp_C6(℃)": "extras.temperature.actual.C6",
    "Actual Temp_C7(℃)": "extras.temperature.actual.C7",
    "Actual Temp_C8(℃)": "extras.temperature.actual.C8",
    
    "Set Temp_C1(℃)": "extras.temperature.set.C1",
    "Set Temp_C2(℃)": "extras.temperature.set.C2",
    "Set Temp_C3(℃)": "extras.temperature.set.C3",
    "Set Temp_C4(℃)": "extras.temperature.set.C4",
    "Set Temp_C5(℃)": "extras.temperature.set.C5",
    "Set Temp_C6(℃)": "extras.temperature.set.C6",
    "Set Temp_C7(℃)": "extras.temperature.set.C7",
    "Set Temp_C8(℃)": "extras.temperature.set.C8",
    
    # 溫度相關（A bucket, Top/Mid/Bottom）
    "Actual Temp_A bucket(℃)": "extras.temperature.actual.A_bucket",
    "Set Temp_A bucket(℃)": "extras.temperature.set.A_bucket",
    "Actual Temp_Top(℃)": "extras.temperature.actual.top",
    "Actual Temp_Mid(℃)": "extras.temperature.actual.mid",
    "Actual Temp_Bottom(℃)": "extras.temperature.actual.bottom",
    "Set Temp_Top(℃)": "extras.temperature.set.top",
    "Set Temp_Mid(℃)": "extras.temperature.set.mid",
    "Set Temp_Bottom(℃)": "extras.temperature.set.bottom",
    
    # 速度、電流等
    "Line Speed(M/min)": "extras.line_speed",
    "Current(A)": "extras.current",
    "Extruder Speed (rpm)": "extras.extruder_speed",
    "Machine_No.": "extras.machine_no",
    "Semi_No.": "lot_no_norm",  # P1 的 LOT NO
}

# ============ P2 欄位映射（分條） ============
P2_FIELD_MAPPING = {
    # 厚度測量（直接屬性）
    "Sheet Width(mm)": "sheet_width",
    "Thicknessss1(μm)": "thickness1",
    "Thicknessss2(μm)": "thickness2",
    "Thicknessss3(μm)": "thickness3",
    "Thicknessss4(μm)": "thickness4",
    "Thicknessss5(μm)": "thickness5",
    "Thicknessss6(μm)": "thickness6",
    "Thicknessss7(μm)": "thickness7",
    
    # 外觀檢查（直接屬性）
    "Appearance": "appearance",
    "rough edge": "rough_edge",
    "Slitting Result": "slitting_result",
    
    # 捲繞機與批次（直接屬性）
    "Winder number": "winder_number",
    "Semi_No.": "lot_no",  # P2 的 LOT NO
}

# ============ P3 欄位映射（生產） ============
P3_FIELD_MAPPING = {
    # 基本資訊（直接屬性）
    "Produce_No.": "product_id",
    "Machine_No.": "machine_no",
    "Mold_No.": "mold_no",
    "Lot_No.": "lot_no",
    
    # 生產參數（從 row_data JSON 提取）
    "E_Value": "row_data.E Value",      # 注意：key 中有空格
    "10PO": "row_data.10PO",
    "Burr": "row_data.Burr",
    "Shift": "row_data.Shift",
    "Iron": "row_data.Iron",
    "Mold": "row_data.Mold",
    "Rubber_Wheel": "row_data.Rubber Wheel",  # 注意：key 中有空格
    "Clean": "row_data.glue",           # 映射到 "glue"
    "Adjustment_Record": "row_data.Adjustment Record",  # 注意：key 中有空格
    "Finish": "row_data.Finish",
}

# ============ P1+P2+P3 組合欄位映射 ============
P1_P2_P3_FIELD_MAPPING = {
    # P1 欄位（與 P1_FIELD_MAPPING 相同，但 Machine_No. 和 Semi_No. 有前綴）
    **{k: v for k, v in P1_FIELD_MAPPING.items() if k not in ["Machine_No.", "Semi_No."]},
    "P1.Machine_No.": "extras.machine_no",  # P1 前綴
    "P1.Semi_No.": "lot_no_norm",  # P1 LOT NO
    
    # P2 欄位（與 P2_FIELD_MAPPING 相同，但 Semi_No. 有前綴）
    **{k: v for k, v in P2_FIELD_MAPPING.items() if k != "Semi_No."},
    "P2.Semi_No.": "p2.lot_no_norm",  # P2 LOT NO（從 P2 record）
    
    # P3 欄位（與 P3_FIELD_MAPPING 相同，但 Machine_No. 有前綴）
    **{k: v for k, v in P3_FIELD_MAPPING.items() if k != "Machine_No."},
    "P3.Machine_No.": "p3.machine_no",  # P3 Machine No（從 P3 record）
}


def get_nested_value(obj: Dict[str, Any], path: str) -> Any:
    """
    從巢狀字典中提取值（支援點記號路徑）
    
    例如：get_nested_value({"a": {"b": {"c": 123}}}, "a.b.c") → 123
    """
    keys = path.split('.')
    current = obj
    
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return None
        else:
            return None
    
    return current
