#!/usr/bin/env python3
"""
簡單的P1/P2/P3測試資料創建腳本

使用curl調用API創建測試資料
"""

import sys

def create_test_data_via_api():
    """通過API創建測試資料"""
    print(" 開始通過API創建 P1/P2/P3 測試資料")
    print("=" * 50)

    # NOTE: legacy query API 已移除（以 v2 為準）。
    # 這個腳本原本依賴一個 legacy 的 create-test-data 端點；為避免誤用，直接中止。
    print(
        "Deprecated: legacy create-test-data endpoint has been removed. "
        "Please seed data via import APIs or database scripts instead."
    )
    sys.exit(1)

if __name__ == "__main__":
    create_test_data_via_api()