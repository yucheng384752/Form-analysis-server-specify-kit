"""測試 Product ID 產生器"""

import sys
from datetime import date

# 測試 Product ID 產生器
from app.services.product_id_generator import (
    ProductIDGenerator,
    generate_product_id,
    parse_product_id,
    validate_product_id
)

print("=" * 60)
print("測試 Product ID 產生器")
print("=" * 60)

generator = ProductIDGenerator()

# 測試 1: 基本產生
print("\n1. 基本產生測試")
product_id = generator.generate(
    production_date=date(2025, 9, 2),
    machine_no="P24",
    mold_no="238-2",
    production_lot=301
)
print(f"   產生: {product_id}")
assert product_id == "2025-09-02_P24_238-2_301", f"格式錯誤: {product_id}"
print("   ✓ 格式正確")

# 測試 2: 從字串產生
print("\n2. 從字串日期產生")
product_id = generator.generate_from_strings(
    production_date_str="2025-09-02",
    machine_no="P24",
    mold_no="238-2",
    production_lot=301
)
print(f"   產生: {product_id}")
assert product_id == "2025-09-02_P24_238-2_301"
print("   ✓ 正確")

# 測試 3: 解析
print("\n3. 解析 Product ID")
parsed = generator.parse("2025-09-02_P24_238-2_301")
print(f"   日期: {parsed['production_date']}")
print(f"   機台: {parsed['machine_no']}")
print(f"   模具號碼: {parsed['mold_no']}")
print(f"   批號: {parsed['production_lot']}")
assert parsed['production_date'] == date(2025, 9, 2)
assert parsed['machine_no'] == "P24"
assert parsed['mold_no'] == "238-2"
assert parsed['production_lot'] == 301
print("   ✓ 解析正確")

# 測試 4: 驗證
print("\n4. 驗證測試")
valid, error = generator.validate("2025-09-02_P24_238-2_301")
assert valid is True
assert error is None
print(f"   有效 Product ID: ✓")

valid, error = generator.validate("invalid_id")
assert valid is False
assert error is not None
print(f"   無效 Product ID: ✓ (錯誤: {error[:30]}...)")

# 測試 5: 快捷函數
print("\n5. 快捷函數測試")
product_id = generate_product_id(date(2025, 1, 15), "P02", "123", 100)
print(f"   產生: {product_id}")
assert product_id == "2025-01-15_P02_123_100"
print("   ✓ 正確")

parsed = parse_product_id(product_id)
assert parsed['production_lot'] == 100
print("   ✓ 解析正確")

valid, _ = validate_product_id(product_id)
assert valid is True
print("   ✓ 驗證正確")

# 測試 6: 邊界情況
print("\n6. 邊界情況測試")
# 批號為 0
product_id = generator.generate(date(2025, 1, 1), "P01", "1", 0)
assert "2025-01-01_P01_1_0" == product_id
print("   ✓ 批號 0: 正確")

# 包含特殊字元的模具號碼
product_id = generator.generate(date(2025, 1, 1), "P99", "ABC-123-X", 999)
assert "2025-01-01_P99_ABC-123-X_999" == product_id
print("   ✓ 特殊字元模具號碼: 正確")

print("\n" + "=" * 60)
print("🎉 Product ID 產生器測試全部通過！")
print("=" * 60)
