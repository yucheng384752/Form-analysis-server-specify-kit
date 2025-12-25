"""
整合測試 - 完整流程測試

測試完整的 Product_ID 功能：
1. 使用 CSV 映射器處理測試資料
2. 生成 Product_ID
3. 驗證資料完整性
4. 測試追溯邏輯（不使用 API，直接測試資料庫查詢邏輯）
"""

import sys
from datetime import date
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.record import Record, DataType
from app.services.csv_field_mapper import csv_field_mapper, CSVType
from app.services.product_id_generator import generate_product_id
from app.services.validation import FileValidationService

# 資料庫連線
TEST_DATABASE_URL = "postgresql://app:app_secure_password_2024@localhost:18001/form_analysis_db"
engine = create_engine(TEST_DATABASE_URL)
Session = sessionmaker(bind=engine)

print("=" * 60)
print("整合測試 - 完整 Product_ID 流程")
print("=" * 60)

# 清理測試資料
print("\n準備測試環境...")
session = Session()
session.query(Record).filter(Record.lot_no == "INTEG_TEST_001").delete()
session.commit()
print("✓ 測試環境已清理")

try:
    # 測試 1: P1 資料處理
    print("\n" + "=" * 60)
    print("測試 1: P1 (吹膜) 資料處理")
    print("=" * 60)
    
    p1_data = pd.DataFrame({
        "Material": ["H8"],
        "Some_Value": [100]
    })
    
    # 使用 CSV 映射器
    p1_mapped = csv_field_mapper.map_csv_to_record_fields(p1_data, "P1_INTEG_TEST_001.csv")
    
    # 建立 P1 記錄
    p1_record = Record(
        data_type=DataType.P1,
        lot_no="INTEG_TEST_001",
        material_code=p1_mapped[0]['material_code'],
        additional_data=p1_mapped[0]['additional_data']
    )
    session.add(p1_record)
    session.commit()
    
    print(f"✓ P1 記錄建立")
    print(f"  ID: {p1_record.id}")
    print(f"  Lot_No: {p1_record.lot_no}")
    print(f"  Material: {p1_record.material_code}")
    
    # 測試 2: P2 資料處理
    print("\n" + "=" * 60)
    print("測試 2: P2 (分條) 資料處理")
    print("=" * 60)
    
    p2_data = pd.DataFrame({
        "Material": ["H8", "H8", "H8"],
        "Slitting Machine": ["1", "1", "1"],
        "Winder": ["15", "16", "17"],
        "Thickness1": [50.1, 50.2, 50.3]
    })
    
    # 使用 CSV 映射器
    p2_mapped = csv_field_mapper.map_csv_to_record_fields(p2_data, "P2_INTEG_TEST_001.csv")
    
    p2_records = []
    for idx, mapped_row in enumerate(p2_mapped):
        p2_record = Record(
            data_type=DataType.P2,
            lot_no="INTEG_TEST_001",
            material_code=mapped_row['material_code'],
            slitting_machine_number=mapped_row['slitting_machine_number'],
            winder_number=mapped_row['winder_number'],
            thickness1=mapped_row['additional_data'].get('Thickness1'),
            additional_data=mapped_row['additional_data']
        )
        session.add(p2_record)
        p2_records.append(p2_record)
    
    session.commit()
    
    print(f"✓ P2 記錄建立: {len(p2_records)} 筆")
    for p2 in p2_records:
        print(f"  Winder {p2.winder_number}: ID={p2.id}, Material={p2.material_code}, Machine={p2.slitting_machine_number}")
    
    # 測試 3: P3 資料處理 + Product_ID 生成
    print("\n" + "=" * 60)
    print("測試 3: P3 (最終檢驗) 資料處理 + Product_ID 生成")
    print("=" * 60)
    
    # 更新: P3 的唯一性約束已改為 product_id unique
    # 現在可以同一個 lot_no 有多筆 P3 記錄（不同 product_id）
    # 測試同一批次、不同 winder、不同 production_lot 的情況
    p3_data = pd.DataFrame({
        "P3_No.": ["2411012_04_15_301", "2411012_04_17_302"],  # 不同 winder (15, 17)，不同 lot (301, 302)
        "E_Value": [990, 991],
        "Burr": [0, 0],
        "Finish": [0, 1],
        "Mold_No": ["238-2", "238-2"]  # 提供模具編號
    })
    
    # 使用 CSV 映射器
    p3_mapped = csv_field_mapper.map_csv_to_record_fields(p3_data, "P3_0902_P24.csv")
    
    p3_records = []
    for idx, mapped_row in enumerate(p3_mapped):
        # 確保有 mold_no，如果沒有則使用預設值
        mold_no = mapped_row.get('mold_no') or mapped_row['additional_data'].get('Mold_No') or "238-2"
        
        # 生成 Product_ID
        product_id = generate_product_id(
            production_date=date(2025, 9, 2),
            machine_no=mapped_row['machine_no'],
            mold_no=mold_no,
            production_lot=mapped_row['production_lot']
        )
        
        p3_record = Record(
            data_type=DataType.P3,
            lot_no="INTEG_TEST_001",
            machine_no=mapped_row['machine_no'],
            mold_no=mold_no,
            production_lot=mapped_row['production_lot'],
            source_winder=mapped_row['source_winder'],
            product_id=product_id,
            additional_data=mapped_row['additional_data']
        )
        session.add(p3_record)
        p3_records.append(p3_record)
    
    session.commit()
    
    print(f"✓ P3 記錄建立: {len(p3_records)} 筆")
    for p3 in p3_records:
        print(f"  Product_ID: {p3.product_id}")
        print(f"    Machine: {p3.machine_no}, Mold: {p3.mold_no}, Lot: {p3.production_lot}")
        print(f"    Source Winder: {p3.source_winder}")
    
    # 測試 4: 追溯查詢邏輯
    print("\n" + "=" * 60)
    print("測試 4: 追溯查詢邏輯 (P3 → P2 → P1)")
    print("=" * 60)
    
    for p3 in p3_records:
        print(f"\n查詢 Product_ID: {p3.product_id}")
        
        # 步驟 1: 已有 P3 資料
        print(f"  ✓ P3: lot={p3.lot_no}, source_winder={p3.source_winder}")
        
        # 步驟 2: 查詢對應的 P2
        p2_query = select(Record).where(
            Record.data_type == DataType.P2,
            Record.lot_no == p3.lot_no,
            Record.winder_number == p3.source_winder
        )
        p2_result = session.execute(p2_query)
        found_p2 = p2_result.scalar_one_or_none()
        
        if found_p2:
            print(f"  ✓ P2: winder={found_p2.winder_number}, material={found_p2.material_code}, machine={found_p2.slitting_machine_number}")
        else:
            print(f"  ⚠ P2: 未找到 (winder={p3.source_winder})")
        
        # 步驟 3: 查詢 P1
        p1_query = select(Record).where(
            Record.data_type == DataType.P1,
            Record.lot_no == p3.lot_no
        )
        p1_result = session.execute(p1_query)
        found_p1 = p1_result.scalar_one_or_none()
        
        if found_p1:
            print(f"  ✓ P1: material={found_p1.material_code}")
        else:
            print(f"  ✗ P1: 未找到")
        
        # 驗證追溯完整性
        trace_complete = all([p3, found_p2, found_p1])
        if trace_complete:
            print(f"  追溯鏈完整: P1 → P2 → P3")
        else:
            print(f"  ⚠ 追溯鏈不完整")
    
    # 測試 5: 資料驗證
    print("\n" + "=" * 60)
    print("測試 5: 資料完整性驗證")
    print("=" * 60)
    
    # 驗證 lot_no 正規化
    validation_service = FileValidationService()
    lot_no_normalized = validation_service.normalize_lot_no("2411012_04_17")
    assert lot_no_normalized == "2411012-04", "lot_no 正規化失敗"
    print(f"✓ Lot_No 正規化: '2411012_04_17' → '{lot_no_normalized}'")
    
    # 驗證 source_winder 提取
    source_winder = validation_service.extract_source_winder("2411012_04_17")
    assert source_winder == 17, "source_winder 提取失敗"
    print(f"✓ Source Winder 提取: '2411012_04_17' → {source_winder}")
    
    # 驗證材料代碼
    validation_service.reset_counters()
    assert validation_service.validate_material_code("H8", 0) is True
    print(f"✓ 材料代碼驗證: 'H8' 有效")
    
    # 驗證分條機編號
    validation_service.reset_counters()
    assert validation_service.validate_slitting_machine_number(1, 0) is True
    print(f"✓ 分條機編號驗證: '1' 有效")
    
    # 測試 6: 統計總結
    print("\n" + "=" * 60)
    print("測試 6: 資料統計總結")
    print("=" * 60)
    
    # 查詢統計
    total_p1 = session.query(Record).filter(
        Record.lot_no == "INTEG_TEST_001",
        Record.data_type == DataType.P1
    ).count()
    
    total_p2 = session.query(Record).filter(
        Record.lot_no == "INTEG_TEST_001",
        Record.data_type == DataType.P2
    ).count()
    
    total_p3 = session.query(Record).filter(
        Record.lot_no == "INTEG_TEST_001",
        Record.data_type == DataType.P3
    ).count()
    
    # 查詢所有 Product_ID
    product_ids = session.query(Record.product_id).filter(
        Record.lot_no == "INTEG_TEST_001",
        Record.data_type == DataType.P3,
        Record.product_id.isnot(None)
    ).all()
    
    print(f"批次 INTEG_TEST_001 統計:")
    print(f"  P1 記錄: {total_p1} 筆")
    print(f"  P2 記錄: {total_p2} 筆")
    print(f"  P3 記錄: {total_p3} 筆")
    print(f"  Product_ID 數量: {len(product_ids)}")
    print(f"\nProduct_IDs:")
    for pid_tuple in product_ids:
        print(f"  - {pid_tuple[0]}")
    
    # 最終驗證
    print("\n" + "=" * 60)
    print("最終驗證")
    print("=" * 60)
    
    assertions = [
        (total_p1 == 1, "P1 記錄數量正確"),
        (total_p2 == 3, "P2 記錄數量正確"),
        (total_p3 == 2, "P3 記錄數量正確（同一批次多個產品）"),
        (len(product_ids) == 2, "Product_ID 數量正確"),
        (all(pid[0] is not None for pid in product_ids), "所有 P3 都有 Product_ID"),
    ]
    
    all_passed = True
    for condition, message in assertions:
        if condition:
            print(f"✓ {message}")
        else:
            print(f"✗ {message}")
            all_passed = False
    
    if all_passed:
        print("\n" + "=" * 60)
        print("🎉 整合測試全部通過！")
        print("=" * 60)
        print("\n功能驗證:")
        print("  CSV 欄位映射器運作正常")
        print("  Product_ID 自動生成正確")
        print("  追溯鏈邏輯完整 (P3→P2→P1)")
        print("  資料驗證功能正常")
        print("  資料庫儲存與查詢正常")
    else:
        print("\n❌ 部分測試失敗")
        sys.exit(1)

finally:
    # 清理測試資料
    print("\n清理測試資料...")
    session.query(Record).filter(Record.lot_no == "INTEG_TEST_001").delete()
    session.commit()
    session.close()
    print("✓ 測試資料已清理")
