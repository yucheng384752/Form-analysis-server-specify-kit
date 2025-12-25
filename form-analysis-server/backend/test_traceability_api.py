"""
測試生產追溯 API

此測試腳本會：
1. 建立測試資料 (P1, P2, P3)
2. 測試 Product_ID 追溯
3. 測試 Lot_No 追溯
4. 測試 Winder 追溯
5. 清理測試資料
"""

import sys
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.record import Record, DataType
from app.services.product_id_generator import generate_product_id

# 建立測試資料庫連線
TEST_DATABASE_URL = "postgresql://app:app_secure_password_2024@localhost:18001/form_analysis_db"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# 覆蓋依賴
app.dependency_overrides[get_db] = get_test_db

client = TestClient(app)

print("=" * 60)
print("測試生產追溯 API")
print("=" * 60)

# 準備測試資料
print("\n準備測試資料...")
db = TestingSessionLocal()

try:
    # 清理舊的測試資料
    db.query(Record).filter(Record.lot_no == "TEST_LOT_001").delete()
    db.commit()
    
    # 建立 P1 記錄
    p1 = Record(
        data_type=DataType.P1,
        lot_no="TEST_LOT_001",
        material_code="H8",
        additional_data={"test": True}
    )
    db.add(p1)
    db.commit()
    print(f"✓ P1 建立: ID={p1.id}, lot_no={p1.lot_no}")
    
    # 建立 P2 記錄 (winder 17)
    p2 = Record(
        data_type=DataType.P2,
        lot_no="TEST_LOT_001",
        material_code="H8",
        slitting_machine_number=1,
        winder_number=17,
        additional_data={"test": True}
    )
    db.add(p2)
    db.commit()
    print(f"✓ P2 建立: ID={p2.id}, winder={p2.winder_number}")
    
    # 建立 P3 記錄
    product_id = generate_product_id(
        production_date=date(2025, 9, 2),
        machine_no="P24",
        mold_no="238-2",
        production_lot=301
    )
    
    p3 = Record(
        data_type=DataType.P3,
        lot_no="TEST_LOT_001",
        machine_no="P24",
        mold_no="238-2",
        production_lot=301,
        source_winder=17,
        product_id=product_id,
        additional_data={"test": True}
    )
    db.add(p3)
    db.commit()
    print(f"✓ P3 建立: ID={p3.id}, product_id={p3.product_id}")
    
    print(f"\n測試資料準備完成！")
    print(f"  Lot_No: TEST_LOT_001")
    print(f"  Product_ID: {product_id}")
    print(f"  追溯鏈: P1 → P2(winder=17) → P3(lot=301)")
    
    # 測試 1: 根據 Product_ID 追溯
    print("\n" + "=" * 60)
    print("測試 1: 根據 Product_ID 追溯")
    print("=" * 60)
    
    response = client.get(f"/api/traceability/product/{product_id}")
    print(f"GET /api/traceability/product/{product_id}")
    print(f"狀態碼: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Product_ID: {data['product_id']}")
        print(f"✓ P3: ID={data['p3']['id']}, machine={data['p3']['machine_no']}, lot={data['p3']['production_lot']}")
        print(f"✓ P2: ID={data['p2']['id']}, winder={data['p2']['winder_number']}")
        print(f"✓ P1: ID={data['p1']['id']}, material={data['p1']['material_code']}")
        print(f"✓ 追溯完整: {data['trace_complete']}")
        
        assert data['product_id'] == product_id
        assert data['p3'] is not None
        assert data['p2'] is not None
        assert data['p1'] is not None
        assert data['trace_complete'] is True
        print("\nProduct_ID 追溯測試通過！")
    else:
        print(f"❌ 錯誤: {response.json()}")
        sys.exit(1)
    
    # 測試 2: 根據 Lot_No 追溯
    print("\n" + "=" * 60)
    print("測試 2: 根據 Lot_No 追溯")
    print("=" * 60)
    
    response = client.get("/api/traceability/lot/TEST_LOT_001")
    print(f"GET /api/traceability/lot/TEST_LOT_001")
    print(f"狀態碼: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Lot_No: {data['lot_no']}")
        print(f"✓ P1: ID={data['p1']['id']}")
        print(f"✓ P2 記錄數: {data['summary']['total_p2']}")
        print(f"✓ P3 記錄數: {data['summary']['total_p3']}")
        print(f"✓ P2 Winders: {data['summary']['p2_winders']}")
        print(f"✓ P3 Lots: {data['summary']['p3_production_lots']}")
        
        assert data['lot_no'] == "TEST_LOT_001"
        assert data['p1'] is not None
        assert data['summary']['total_p2'] >= 1
        assert data['summary']['total_p3'] >= 1
        print("\nLot_No 追溯測試通過！")
    else:
        print(f"❌ 錯誤: {response.json()}")
        sys.exit(1)
    
    # 測試 3: 根據 Winder 追溯
    print("\n" + "=" * 60)
    print("測試 3: 根據 Winder 追溯")
    print("=" * 60)
    
    response = client.get("/api/traceability/winder/TEST_LOT_001/17")
    print(f"GET /api/traceability/winder/TEST_LOT_001/17")
    print(f"狀態碼: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Lot_No: {data['lot_no']}")
        print(f"✓ Winder: {data['winder_number']}")
        print(f"✓ P2: ID={data['p2']['id']}, winder={data['p2']['winder_number']}")
        print(f"✓ P1: ID={data['p1']['id']}")
        print(f"✓ P3 記錄數: {data['summary']['total_p3_from_this_winder']}")
        
        assert data['lot_no'] == "TEST_LOT_001"
        assert data['winder_number'] == 17
        assert data['p2'] is not None
        assert data['p1'] is not None
        print("\nWinder 追溯測試通過！")
    else:
        print(f"❌ 錯誤: {response.json()}")
        sys.exit(1)
    
    # 測試 4: 錯誤處理 - 不存在的 Product_ID
    print("\n" + "=" * 60)
    print("測試 4: 錯誤處理")
    print("=" * 60)
    
    response = client.get("/api/traceability/product/2099-01-01_XXX_999_999")
    print(f"GET /api/traceability/product/2099-01-01_XXX_999_999")
    print(f"狀態碼: {response.status_code}")
    assert response.status_code == 404
    print(f"✓ 正確回傳 404: {response.json()['detail']}")
    
    response = client.get("/api/traceability/lot/NONEXISTENT")
    print(f"GET /api/traceability/lot/NONEXISTENT")
    print(f"狀態碼: {response.status_code}")
    assert response.status_code == 404
    print(f"✓ 正確回傳 404: {response.json()['detail']}")
    
    print("\n錯誤處理測試通過！")
    
    print("\n" + "=" * 60)
    print("🎉 所有追溯 API 測試通過！")
    print("=" * 60)
    
finally:
    # 清理測試資料
    print("\n清理測試資料...")
    db.query(Record).filter(Record.lot_no == "TEST_LOT_001").delete()
    db.commit()
    db.close()
    print("✓ 測試資料已清理")
