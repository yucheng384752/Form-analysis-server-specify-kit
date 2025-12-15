import sys
sys.path.append('/app')

from app.services.validation import FileValidationService

# 建立驗證服務實例
validator = FileValidationService()

# 測試批號正規化
test_cases = [
    '2507173_02_17',
    '2507173_02_18',
    '2411012_04_31_302',
    '2507173_02',
]

print("=" * 80)
print("測試批號正規化函數")
print("=" * 80)

for test in test_cases:
    normalized = validator.normalize_lot_no(test)
    matches_standard = validator.LOT_NO_PATTERN.match(normalized) is not None
    print(f"輸入: {test:25} → 正規化: {normalized:15} → 驗證: {'✓' if matches_standard else '✗'}")
