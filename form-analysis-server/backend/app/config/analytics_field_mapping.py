"""
Analytics API 欄位映射配置
定義 P1/P2/P3 到扁平化輸出的映射關係

新規定：
1. 資料庫內沒有的值填入 null（而非省略或預設值）
2. 空資料維持空陣列 []（如 P3.extras.rows == []）
"""

# ============ P1 欄位映射 ============
P1_FIELD_MAPPING = {
    # 基本資訊（保證存在）
    'timestamp': 'extras.production_date',        # P1 生產時間（從 extras）
    'location': lambda r: '',                      # P1 固定空字串
    
    # LOT 資訊
    'LOT NO.': 'lot_no_norm',                      # 標準化 LOT NO
    'P1.Specification': 'extras.specification',    # 規格（JSONB）
    'P1.Material': 'extras.material',              # 材料
    
    # 半成品資訊（可能為 null）
    'Semi-finished Sheet Width(mm)': 'extras.sheet_width',      # null if missing
    'Semi-finished Length(M)': 'extras.length',                 # null if missing
    'Weight(Kg)': 'extras.weight',                              # null if missing
    
    # 溫度參數（C1-C8，可能為 null）
    'Actual Temp_C1(°C)': 'extras.temperature.actual.C1',
    'Actual Temp_C2(°C)': 'extras.temperature.actual.C2',
    'Actual Temp_C3(°C)': 'extras.temperature.actual.C3',
    'Actual Temp_C4(°C)': 'extras.temperature.actual.C4',
    'Actual Temp_C5(°C)': 'extras.temperature.actual.C5',
    'Actual Temp_C6(°C)': 'extras.temperature.actual.C6',
    'Actual Temp_C7(°C)': 'extras.temperature.actual.C7',
    'Actual Temp_C8(°C)': 'extras.temperature.actual.C8',
    
    'Set Temp_C1(°C)': 'extras.temperature.set.C1',
    'Set Temp_C2(°C)': 'extras.temperature.set.C2',
    'Set Temp_C3(°C)': 'extras.temperature.set.C3',
    'Set Temp_C4(°C)': 'extras.temperature.set.C4',
    'Set Temp_C5(°C)': 'extras.temperature.set.C5',
    'Set Temp_C6(°C)': 'extras.temperature.set.C6',
    'Set Temp_C7(°C)': 'extras.temperature.set.C7',
    'Set Temp_C8(°C)': 'extras.temperature.set.C8',
    
    # A bucket 溫度
    'Actual Temp_A bucket(°C)': 'extras.temperature.actual.A_bucket',
    'Set Temp_A bucket(°C)': 'extras.temperature.set.A_bucket',
    
    # Top/Mid/Bottom 溫度
    'Actual Temp_Top(°C)': 'extras.temperature.actual.top',
    'Actual Temp_Mid(°C)': 'extras.temperature.actual.mid',
    'Actual Temp_Bottom(°C)': 'extras.temperature.actual.bottom',
    'Set Temp_Top(°C)': 'extras.temperature.set.top',
    'Set Temp_Mid(°C)': 'extras.temperature.set.mid',
    'Set Temp_Bottom(°C)': 'extras.temperature.set.bottom',
    
    # 機器參數（可能為 null）
    'Line Speed(M/min)': 'extras.line_speed',
    'Current(A)': 'extras.current',
    'Extruder Speed (rpm)': 'extras.extruder_speed',
    'Frame (cm)': 'extras.frame',
    
    # 機器編號
    'Machine_No.': 'extras.machine_no',            # null if missing
    'Semi_No.': 'extras.semi_no',                  # null if missing
}

# ============ P2 欄位映射 ============
P2_FIELD_MAPPING = {
    # 基本資訊
    'format': lambda r: 'P2',                      # 固定 "P2"
    'P2.Material': 'extras.material',              # null if missing
    'Semi-finished No.': 'lot_no_norm',            # P2 LOT NO
    
    # 分條資訊（可能為 null）
    'Slitting date': 'extras.分條時間',             # P2 分條時間（從 extras）
    'Slitting machine': 'extras.slitting_machine',
    
    # Winder 資訊（需透過 source_winder 匹配）
    'Winder number': 'winder_number',              # 捲繞機號碼
    'Board Width(mm)': 'extras.board_width',       # null if missing
    
    # 厚度資訊
    'Thicknessss High(μm)': 'extras.thickness.high',  # null if missing
    'Thicknessss Low(μm)': 'extras.thickness.low',    # null if missing
    
    # 品質檢測（可能為 null 或空字串）
    'Appearance': 'extras.appearance',
    'rough edge': 'extras.rough_edge',
    'Striped Results': 'extras.striped_results',
}

# ============ P3 欄位映射 ============
P3_FIELD_MAPPING = {
    # 基本資訊
    'type': lambda r: 'P3',                        # 固定 "P3"
    'Production Date': 'production_date_yyyymmdd', # P3 生產日期（需轉 ISO 8601）
    
    # 產品規格
    'P3.Specification': 'extras.specification',
    'BottomTape': 'extras.bottom_tape',            # null if missing
    
    # 機器資訊
    'Machine No.': 'extras.machine_no',
    'Mold No.': 'extras.mold_no',                  # null if missing
    
    # 批次資訊（來自 extras.rows[] 各元素）
    'lot': 'row.lot',                              # 從 rows[i].lot
    'AdjustmentRecord': 'row.adjustment_record',   # 從 rows[i]
    'Finish': 'row.finish',                        # 從 rows[i]
    'operator': 'row.operator',                    # 從 rows[i]
    'Produce_No.': 'row.produce_no',               # 從 rows[i]
    'Specification': 'row.specification',          # 從 rows[i]
}

# ============ 輸出欄位順序（70+ 欄位）============
OUTPUT_FIELD_ORDER = [
    # ===== P3 核心欄位（5 個）=====
    'timestamp',                    # P3 生產時間
    'type',                         # 固定 "P3"
    'location',                     # 固定空字串
    'LOT NO.',                      # P3 批號
    
    # ===== P1 追溯欄位（32 個）=====
    'P1.Specification',
    'P1.Material',
    'Semi-finished Sheet Width(mm)',
    'Semi-finished Length(M)',
    'Weight(Kg)',
    
    # 溫度參數（16 個實際溫度 + 16 個設定溫度）
    'Actual Temp_C1(°C)', 'Actual Temp_C2(°C)', 'Actual Temp_C3(°C)', 'Actual Temp_C4(°C)',
    'Actual Temp_C5(°C)', 'Actual Temp_C6(°C)', 'Actual Temp_C7(°C)', 'Actual Temp_C8(°C)',
    'Set Temp_C1(°C)', 'Set Temp_C2(°C)', 'Set Temp_C3(°C)', 'Set Temp_C4(°C)',
    'Set Temp_C5(°C)', 'Set Temp_C6(°C)', 'Set Temp_C7(°C)', 'Set Temp_C8(°C)',
    'Actual Temp_A bucket(°C)', 'Set Temp_A bucket(°C)',
    'Actual Temp_Top(°C)', 'Actual Temp_Mid(°C)', 'Actual Temp_Bottom(°C)',
    'Set Temp_Top(°C)', 'Set Temp_Mid(°C)', 'Set Temp_Bottom(°C)',
    
    # 機器參數
    'Line Speed(M/min)',
    'Current(A)',
    'Extruder Speed (rpm)',
    'Frame (cm)',
    'Machine_No.',
    'Semi_No.',
    
    # ===== P2 追溯欄位（13 個）=====
    'format',
    'P2.Material',
    'Semi-finished No.',
    'Slitting date',
    'Slitting machine',
    'Winder number',
    'Board Width(mm)',
    'Thicknessss High(μm)',
    'Thicknessss Low(μm)',
    'Appearance',
    'rough edge',
    'Striped Results',
    
    # ===== P3 產品資訊（14 個）=====
    'Production Date',
    'P3.Specification',
    'BottomTape',
    'Machine No.',
    'Mold No.',
    'lot',
    'AdjustmentRecord',
    'Finish',
    'operator',
    'Produce_No.',
    'Specification',
]

# ============ Null 處理邏輯 ============
def get_nested_value(obj: dict, path: str, default=None):
    """
    從巢狀字典取值，支援點記號路徑（如 'extras.temperature.actual.C1'）
    
    新規定：
    - 找不到欄位回傳 None（而非預設值或省略）
    - 空字串視為有效值（不轉為 None）
    """
    keys = path.split('.')
    current = obj
    
    for key in keys:
        if not isinstance(current, dict):
            return None  # 找不到欄位
        
        if key not in current:
            return None  # 找不到欄位
        
        current = current[key]
    
    # 特殊處理：空字串視為有效值
    if current == '':
        return ''
    
    # None 或缺失值回傳 None
    return current if current is not None else None


# ============ 空陣列處理 ============
"""
新規定：空資料維持空陣列

範例：
- P3.extras.rows == [] → 回傳 {"data": [], "count": 0, "has_data": false}
- P3.extras.rows == [row1, row2] → 回傳 {"data": [扁平化記錄1, 2], "count": 2, "has_data": true}

不會將空陣列轉為 null 或省略
"""

# ============ 預設值配置 ============
DEFAULT_VALUES = {
    # 字串型欄位：空字串（除非明確不存在則為 null）
    'location': '',
    'type': 'P3',
    'format': 'P2',
    
    # 數值型欄位：null（不使用 0 作為預設）
    # 見 analytics_config.py 中的 DEFAULT_NULL_FIELDS
    
    # 日期型欄位：null（不使用當前時間）
}
