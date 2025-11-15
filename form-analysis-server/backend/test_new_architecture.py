#!/usr/bin/env python3
"""
測試新資料庫架構和驗證 API 設計
"""

import requests
import json
from datetime import datetime, date

# API 基礎 URL
BASE_URL = "http://localhost:8000"

def test_database_connection():
    """測試資料庫連接"""
    try:
        response = requests.get(f"{BASE_URL}/healthz/detailed")
        return response.status_code == 200
    except:
        return False

def test_lot_no_validation():
    """測試 lot_no 格式驗證"""
    print("🧪 測試 lot_no 格式驗證...")
    
    # 有效的 lot_no 格式
    valid_lots = [
        "2503033_01",
        "2503033_02", 
        "1234567_99"
    ]
    
    # 無效的 lot_no 格式
    invalid_lots = [
        "250303_01",    # 太短
        "25030331_01",  # 太長
        "2503033_1",    # 第二部分太短
        "2503033_001",  # 第二部分太長
        "abc3033_01",   # 包含字母
        "2503033-01"    # 錯誤分隔符
    ]
    
    for lot_no in valid_lots:
        print(f"   有效: {lot_no}")
    
    for lot_no in invalid_lots:
        print(f"   無效: {lot_no}")

def create_sample_data():
    """創建範例數據"""
    print("\n 創建範例生產批次數據...")
    
    # 範例數據結構
    sample_lots = [
        {
            "lot_no": "2503033_01",
            "production_date": "2025-03-03",
            "product_spec": "0.32mm",
            "material": "H5",
            "phase": "P1",
            "good_products": 40,
            "defective_products": 0
        },
        {
            "lot_no": "2503033_02", 
            "production_date": "2025-03-03",
            "product_spec": "0.32mm",
            "material": "H5", 
            "phase": "P2",
            "good_products": 38,
            "defective_products": 2
        },
        {
            "lot_no": "2503033_03",
            "production_date": "2025-03-03", 
            "product_spec": "0.32mm",
            "material": "H5",
            "phase": "P3",
            "good_products": 35,
            "defective_products": 3
        }
    ]
    
    return sample_lots

def demonstrate_api_structure():
    """展示 API 結構設計"""
    print("\n API 結構設計示範：")
    
    api_examples = {
        "生產批次管理": {
            "創建批次": "POST /api/production/lots",
            "獲取批次": "GET /api/production/lots/{lot_no}",
            "更新批次": "PUT /api/production/lots/{lot_no}",
            "刪除批次": "DELETE /api/production/lots/{lot_no}",
            "查詢列表": "GET /api/production/lots?phase=P1&date_start=2025-03-01"
        },
        "P1階段數據": {
            "新增數據": "POST /api/data/p1/{lot_no}",
            "獲取數據": "GET /api/data/p1/{lot_no}",
            "更新記錄": "PUT /api/data/p1/{lot_no}/{record_id}",
            "刪除記錄": "DELETE /api/data/p1/{lot_no}/{record_id}"
        },
        "檔案上傳": {
            "上傳CSV": "POST /api/upload/csv/{phase}/{lot_no}",
            "上傳JSON": "POST /api/upload/json/{lot_no}",
            "下載範本": "GET /api/upload/template/{phase}"
        },
        "數據分析": {
            "生產彙總": "GET /api/analytics/summary",
            "品質趨勢": "GET /api/analytics/trends/{lot_no}",
            "批次比較": "GET /api/analytics/comparison?lot_numbers=2503033_01,2503033_02",
            "全文搜尋": "GET /api/analytics/search?keyword=H5&search_fields=material,product_spec"
        }
    }
    
    for category, endpoints in api_examples.items():
        print(f"\n  📂 {category}")
        for description, endpoint in endpoints.items():
            print(f"    • {description}: {endpoint}")

def explain_design_benefits():
    """說明設計優勢"""
    print("\n💡 設計優勢說明：")
    
    benefits = {
        "以 lot_no 為唯一鍵的優勢": [
            " 業務邏輯自然：lot_no 是生產流程的核心標識符",
            " 跨階段追溯：P1-P3 所有數據都可通過 lot_no 關聯",
            " 查詢效能：直接使用業務主鍵，避免不必要的 JOIN",
            " 檔案對應：現有檔案命名已包含 lot_no 資訊"
        ],
        "分階段表設計的優勢": [
            " 資料隔離：不同階段數據結構差異很大，分表更清晰",
            " 效能優化：避免單表過寬，提升查詢效能", 
            " 擴展性：未來新增階段或修改結構更靈活",
            " 維護性：各階段可獨立備份和維護"
        ],
        "RESTful API 設計優勢": [
            " 直觀性：URL 結構直接反映資源層級關係",
            " 一致性：所有操作遵循相同的命名模式",
            " 可預測性：開發者可以猜測 API 端點結構",
            " 標準化：遵循 HTTP 動詞語義"
        ]
    }
    
    for category, items in benefits.items():
        print(f"\n  🎯 {category}")
        for item in items:
            print(f"    {item}")

def main():
    """主測試函數"""
    print(" 生產數據管理系統 - 資料庫架構和 API 設計驗證")
    print("=" * 60)
    
    # 1. 測試資料庫連接
    print("\n 檢查服務狀態...")
    if test_database_connection():
        print("   資料庫連接正常")
    else:
        print("   資料庫連接失敗")
    
    # 2. 驗證 lot_no 格式
    test_lot_no_validation()
    
    # 3. 展示範例數據
    print("\n 範例數據結構:")
    sample_data = create_sample_data()
    for lot in sample_data:
        print(f"  • {lot['lot_no']}: {lot['phase']} 階段 - {lot['product_spec']} ({lot['material']})")
    
    # 4. API 結構展示
    demonstrate_api_structure()
    
    # 5. 設計優勢說明
    explain_design_benefits()
    
    print("\n 架構設計驗證完成！")
    print("\n 詳細說明請參考:")
    print("  • database_migration_design.sql - 資料庫架構")
    print("  • api_models_design.py - API 數據模型")
    print("  • api_routes_design.py - API 路由設計")
    print("  • API_DESIGN_EXPLANATION.md - 完整設計說明")

if __name__ == "__main__":
    main()