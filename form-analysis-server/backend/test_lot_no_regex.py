"""
快速測試批號正規化功能
"""
import re

# 批號正規表示式：7位數字_2位數字（標準格式）
LOT_NO_PATTERN = re.compile(r'^\d{7}_\d{2}$')

# 批號彈性格式：支援 7+2 或 7+2+任意後續 (例如 7+2+2, 7+2+2+3)
LOT_NO_FLEXIBLE_PATTERN = re.compile(r'^(\d{7}_\d{2})(?:_.+)?$')

def normalize_lot_no(lot_no_value):
    """正規化批號"""
    if not lot_no_value:
        return ""
    
    lot_no_str = str(lot_no_value).strip()
    
    # 檢查是否符合彈性格式（7+2 或 7+2+x）
    match = LOT_NO_FLEXIBLE_PATTERN.match(lot_no_str)
    if match:
        # 提取前 9 碼（7位數字_2位數字）
        return match.group(1)
    
    # 如果不符合任何格式，返回原值（讓後續驗證處理）
    return lot_no_str

# 測試案例
test_cases = [
    "2507173_02",       # 標準 7+2 格式
    "2507173_02_17",    # 7+2+2 格式
    "2507173_02_18",    # 7+2+2 格式
    "2411012_04",       # 標準 7+2 格式
    "2411012_04_31_302", # 7+2+2+3 格式
    " 2507173_02_17 ",  # 帶空格
    "250717_02",        # 錯誤：只有6個數字
    "2507173_2",        # 錯誤：只有1個數字
    "abc_def",          # 錯誤：非數字
]

print("=" * 80)
print("批號正規化測試")
print("=" * 80)

for test_lot in test_cases:
    print(f"\n原始值: '{test_lot}'")
    
    # 正規化
    normalized = normalize_lot_no(test_lot)
    print(f"正規化後: '{normalized}'")
    
    # 檢查彈性模式匹配
    flexible_match = LOT_NO_FLEXIBLE_PATTERN.match(str(test_lot).strip())
    print(f"彈性模式匹配: {flexible_match is not None}")
    if flexible_match:
        print(f"  提取的批號: '{flexible_match.group(1)}'")
    
    # 檢查標準格式匹配
    standard_match = LOT_NO_PATTERN.match(normalized)
    print(f"標準格式驗證: {standard_match is not None}")
    
    if standard_match:
        print("✅ 通過驗證")
    else:
        print("❌ 驗證失敗")

print("\n" + "=" * 80)
