"""
P3 Items 實作測試腳本
測試 P3Item 模型、Record 關聯和匯入邏輯
"""

import sys
import os

# 添加後端路徑到 sys.path
backend_path = os.path.join(os.path.dirname(__file__), 'form-analysis-server', 'backend')
sys.path.insert(0, backend_path)

def test_imports():
    """測試 1: 檢查所有導入是否正確"""
    print("=" * 60)
    print("測試 1: 導入檢查")
    print("=" * 60)
    
    errors = []
    
    try:
        from app.models.p3_item import P3Item
        print(" P3Item 模型導入成功")
    except Exception as e:
        errors.append(f"P3Item 導入失敗: {e}")
        print(errors[-1])
    
    try:
        from app.models.record import Record
        print(" Record 模型導入成功")
    except Exception as e:
        errors.append(f"Record 導入失敗: {e}")
        print(errors[-1])
    
    try:
        from app.api.routes_import import router
        print(" routes_import 導入成功")
    except Exception as e:
        errors.append(f"routes_import 導入失敗: {e}")
        print(errors[-1])
    
    return errors

def test_p3item_model():
    """測試 2: 驗證 P3Item 模型定義"""
    print("\n" + "=" * 60)
    print("測試 2: P3Item 模型結構驗證")
    print("=" * 60)
    
    errors = []
    
    try:
        from app.models.p3_item import P3Item
        from sqlalchemy.inspection import inspect
        
        # 檢查必要欄位
        required_fields = [
            'id', 'record_id', 'product_id', 'lot_no', 
            'machine_no', 'mold_no', 'specification', 
            'bottom_tape_lot', 'row_no', 'row_data',
            'created_at', 'updated_at'
        ]
        
        mapper = inspect(P3Item)
        columns = {col.key for col in mapper.columns}
        
        for field in required_fields:
            if field in columns:
                print(f" 欄位 '{field}' 存在")
            else:
                errors.append(f"欄位 '{field}' 不存在")
                print(errors[-1])
        
        # 檢查索引
        print("\n檢查索引:")
        if hasattr(P3Item, '__table__'):
            indexes = P3Item.__table__.indexes
            print(f" 找到 {len(indexes)} 個索引")
            for idx in indexes:
                print(f"   - {idx.name}")
        else:
            errors.append("無法訪問 __table__ 屬性")
            print(errors[-1])
        
    except Exception as e:
        errors.append(f"P3Item 模型驗證失敗: {e}")
        print(errors[-1])
    
    return errors

def test_record_relationship():
    """測試 3: 驗證 Record 與 P3Item 的關聯"""
    print("\n" + "=" * 60)
    print("測試 3: Record ↔ P3Item 關聯驗證")
    print("=" * 60)
    
    errors = []
    
    try:
        from app.models.record import Record
        from app.models.p3_item import P3Item
        from sqlalchemy.inspection import inspect
        
        # 檢查 Record 的 p3_items relationship
        mapper = inspect(Record)
        relationships = {rel.key for rel in mapper.relationships}
        
        if 'p3_items' in relationships:
            print(" Record 模型有 'p3_items' relationship")
            
            # 獲取 relationship 詳細資訊
            rel = mapper.relationships['p3_items']
            print(f"   - Target: {rel.mapper.class_.__name__}")
            print(f"   - Back populates: {rel.back_populates}")
            print(f"   - Cascade: {rel.cascade}")
        else:
            errors.append("Record 模型缺少 'p3_items' relationship")
            print(errors[-1])
        
        # 檢查 P3Item 的 record relationship
        mapper = inspect(P3Item)
        relationships = {rel.key for rel in mapper.relationships}
        
        if 'record' in relationships:
            print(" P3Item 模型有 'record' relationship")
            
            # 獲取 relationship 詳細資訊
            rel = mapper.relationships['record']
            print(f"   - Target: {rel.mapper.class_.__name__}")
            print(f"   - Back populates: {rel.back_populates}")
        else:
            errors.append("P3Item 模型缺少 'record' relationship")
            print(errors[-1])
        
    except Exception as e:
        errors.append(f"Relationship 驗證失敗: {e}")
        print(errors[-1])
    
    return errors

def test_import_logic():
    """測試 4: 檢查 routes_import.py 中的 P3 邏輯"""
    print("\n" + "=" * 60)
    print("測試 4: P3 匯入邏輯檢查")
    print("=" * 60)
    
    errors = []
    
    try:
        # 讀取 routes_import.py 檔案內容
        import_file = os.path.join(
            backend_path, 
            'app', 'api', 'routes_import.py'
        )
        
        with open(import_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查關鍵程式碼片段
        checks = [
            ('P3Item import', 'from app.models.p3_item import P3Item'),
            ('P3Item 創建邏輯', 'p3_item = P3Item('),
            ('record_id 關聯', 'record_id='),
            ('product_id 生成', 'item_product_id'),
            ('source_winder 提取', 'source_winder'),
            ('db.add(p3_item)', 'db.add(p3_item)'),
        ]
        
        for check_name, check_str in checks:
            if check_str in content:
                print(f" {check_name} 存在")
            else:
                errors.append(f"{check_name} 不存在")
                print(errors[-1])
        
        # 檢查是否有基本的邏輯結構
        if 'for row_no, row_data in enumerate(all_rows, start=1):' in content:
            print(" 逐列處理邏輯存在")
        else:
            errors.append("逐列處理邏輯不存在")
            print(errors[-1])
        
    except Exception as e:
        errors.append(f"匯入邏輯檢查失敗: {e}")
        print(errors[-1])
    
    return errors

def test_database_migration_sql():
    """測試 5: 驗證資料庫遷移 SQL"""
    print("\n" + "=" * 60)
    print("測試 5: 資料庫遷移 SQL 驗證")
    print("=" * 60)
    
    errors = []
    
    try:
        summary_file = os.path.join(
            os.path.dirname(__file__),
            'P3_ITEMS_IMPLEMENTATION_SUMMARY.md'
        )
        
        if os.path.exists(summary_file):
            with open(summary_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 檢查 SQL 關鍵元素
            sql_checks = [
                ('CREATE TABLE', 'CREATE TABLE p3_items'),
                ('PRIMARY KEY', 'PRIMARY KEY'),
                ('FOREIGN KEY', 'REFERENCES records(id)'),
                ('CASCADE DELETE', 'ON DELETE CASCADE'),
                ('索引定義', 'CREATE INDEX'),
                ('UNIQUE 約束', 'UNIQUE'),
            ]
            
            for check_name, check_str in sql_checks:
                if check_str in content:
                    print(f" SQL 包含 {check_name}")
                else:
                    errors.append(f" SQL 可能缺少 {check_name}")
                    print(errors[-1])
        else:
            errors.append("P3_ITEMS_IMPLEMENTATION_SUMMARY.md 不存在")
            print(errors[-1])
        
    except Exception as e:
        errors.append(f"SQL 驗證失敗: {e}")
        print(errors[-1])
    
    return errors

def main():
    """執行所有測試"""
    print("\n" + "=" * 60)
    print("P3 ITEMS 實作測試")
    print("=" * 60 + "\n")
    
    all_errors = []
    
    # 執行所有測試
    all_errors.extend(test_imports())
    all_errors.extend(test_p3item_model())
    all_errors.extend(test_record_relationship())
    all_errors.extend(test_import_logic())
    all_errors.extend(test_database_migration_sql())
    
    # 總結
    print("\n" + "=" * 60)
    print("測試總結")
    print("=" * 60)
    
    if not all_errors:
        print(" 所有測試通過！")
        return 0
    else:
        print(f"發現 {len(all_errors)} 個問題:")
        for i, error in enumerate(all_errors, 1):
            print(f"{i}. {error}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
