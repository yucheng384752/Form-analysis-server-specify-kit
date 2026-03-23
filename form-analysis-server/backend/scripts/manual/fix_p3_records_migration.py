"""
修復 P3 資料遷移腳本
將 legacy records 表中的 P3 記錄遷移到 p3_records 表

執行方式：
    python fix_p3_records_migration.py

功能：
1. 查找 legacy records 表中尚未遷移到 p3_records 的 P3 記錄
2. 建立對應的 p3_records 記錄
3. 驗證資料完整性
"""

import asyncio
import sys
from pathlib import Path

# 將 backend 目錄加入路徑
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import init_db, get_db_context
from app.models.p3_record import P3Record
import uuid
from datetime import datetime


async def check_missing_records(session: AsyncSession):
    """檢查哪些 legacy P3 records 尚未遷移到 p3_records"""
    query = text("""
        SELECT 
            r.id as legacy_id,
            r.lot_no,
            r.created_at,
            r.additional_data as extras,
            COUNT(p3i.id) as item_count
        FROM records r
        LEFT JOIN p3_items p3i ON p3i.record_id = r.id
        LEFT JOIN p3_records p3r ON p3r.lot_no_raw = r.lot_no
        WHERE r.data_type = 'P3'
          AND p3r.id IS NULL
        GROUP BY r.id, r.lot_no, r.created_at, r.additional_data
        ORDER BY r.created_at DESC
    """)
    
    result = await session.execute(query)
    missing_records = result.fetchall()
    
    return missing_records


async def migrate_record(session: AsyncSession, legacy_record):
    """將一筆 legacy record 遷移到 p3_records"""
    lot_no_raw = legacy_record.lot_no
    
    # 移除 lot_no 中的 '_' 和 '-' 並轉為整數
    lot_no_norm = int(lot_no_raw.replace('_', '').replace('-', ''))
    
    # 從 tenants 表獲取 tenant_id
    tenant_query = text("SELECT id FROM tenants LIMIT 1")
    tenant_result = await session.execute(tenant_query)
    tenant_id = tenant_result.scalar()
    
    if not tenant_id:
        raise ValueError("無法取得 tenant_id")
    
    # 從 p3_items 取得 production_date, machine_no, mold_no
    # 使用 MIN 取得最早的生產日期，MODE() 取得最常見的 machine_no 和 mold_no
    items_query = text("""
        SELECT 
            MIN(production_date) as production_date,
            machine_no,
            mold_no
        FROM p3_items
        WHERE record_id = :record_id
        GROUP BY machine_no, mold_no
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """)
    
    items_result = await session.execute(items_query, {"record_id": str(legacy_record.legacy_id)})
    item_data = items_result.fetchone()
    
    if not item_data:
        raise ValueError(f"找不到 lot_no={lot_no_raw} 的 p3_items 資料")
    
    # 將日期轉為 YYYYMMDD 格式
    production_date = item_data.production_date
    production_date_yyyymmdd = int(production_date.strftime("%Y%m%d"))
    machine_no = item_data.machine_no
    mold_no = item_data.mold_no
    
    # 生成 product_id: YYYY-MM-DD_machine_mold_lot
    # 從 lot_no 取得最後的 lot 編號（例如 2507243_01 → 01）
    lot_parts = lot_no_raw.split('_')
    lot_number = lot_parts[-1] if len(lot_parts) > 1 else lot_no_raw
    product_id = f"{production_date.strftime('%Y%m%d')}-{machine_no}-{mold_no}-{lot_number}"
    
    # 建立新的 P3Record
    new_record = P3Record(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        lot_no_raw=lot_no_raw,
        lot_no_norm=lot_no_norm,
        production_date_yyyymmdd=production_date_yyyymmdd,
        machine_no=machine_no,
        mold_no=mold_no,
        product_id=product_id,
        schema_version_id=None,
        extras=legacy_record.extras or {},
        created_at=legacy_record.created_at
    )
    
    session.add(new_record)
    
    return new_record


async def main():
    """主要執行流程"""
    print("=" * 60)
    print("P3 資料遷移修復腳本")
    print("=" * 60)
    print()
    
    # 初始化資料庫
    await init_db()
    
    async with get_db_context() as session:
        try:
            # 1. 檢查缺失的記錄
            print("步驟 1: 檢查 legacy records 中尚未遷移的 P3 記錄...")
            missing_records = await check_missing_records(session)
            
            if not missing_records:
                print("沒有需要遷移的記錄！")
                return
            
            print(f"📋 發現 {len(missing_records)} 筆需要遷移的記錄：")
            print()
            for record in missing_records:
                print(f"  - lot_no: {record.lot_no}")
                print(f"    legacy_id: {record.legacy_id}")
                print(f"    items 數量: {record.item_count}")
                print(f"    建立時間: {record.created_at}")
                print()
            
            # 2. 確認是否執行遷移
            print("步驟 2: 執行遷移")
            # 自動確認執行（避免互動模式問題）
            print("⚙️  自動執行遷移...")
            response = 'yes'
            
            if response != 'yes':
                print("取消遷移")
                return
            
            # 3. 執行遷移
            print()
            print("開始遷移...")
            migrated_count = 0
            
            for legacy_record in missing_records:
                try:
                    new_record = await migrate_record(session, legacy_record)
                    print(f"已遷移: {legacy_record.lot_no} -> p3_records.id={new_record.id}")
                    migrated_count += 1
                except Exception as e:
                    print(f"遷移失敗: {legacy_record.lot_no}, 錯誤: {e}")
            
            # 4. 提交變更
            if migrated_count > 0:
                await session.commit()
                print()
                print(f"成功遷移 {migrated_count} 筆記錄")
            else:
                print()
                print("沒有成功遷移任何記錄")
            
            # 5. 驗證結果
            print()
            print("步驟 3: 驗證遷移結果...")
            remaining = await check_missing_records(session)
            
            if not remaining:
                print("驗證成功！所有 P3 records 已完整遷移")
            else:
                print(f"⚠️  仍有 {len(remaining)} 筆記錄未遷移")
            
            # 6. 顯示統計
            print()
            print("=" * 60)
            print("遷移統計")
            print("=" * 60)
            
            # 統計 legacy records
            legacy_count_query = text("SELECT COUNT(*) FROM records WHERE data_type = 'P3'")
            legacy_result = await session.execute(legacy_count_query)
            legacy_count = legacy_result.scalar()
            
            # 統計 p3_records
            v2_count_query = select(P3Record)
            v2_result = await session.execute(v2_count_query)
            v2_count = len(v2_result.scalars().all())
            
            # 統計 p3_items
            items_count_query = text("SELECT COUNT(*) FROM p3_items")
            items_result = await session.execute(items_count_query)
            items_count = items_result.scalar()
            
            print(f"Legacy records (P3): {legacy_count} 筆")
            print(f"V2 p3_records: {v2_count} 筆")
            print(f"p3_items: {items_count} 筆")
            print()
            
            if legacy_count == v2_count:
                print("資料完整性：所有 legacy P3 records 已同步到 p3_records")
            else:
                print(f"⚠️  資料完整性：仍有 {legacy_count - v2_count} 筆記錄未同步")
            
        except Exception as e:
            print(f"執行錯誤: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
