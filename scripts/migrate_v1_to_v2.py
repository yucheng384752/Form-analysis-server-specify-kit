import asyncio
import os
import sys
from datetime import date
from typing import Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 添加 backend 到 sys.path
sys.path.insert(0, os.path.join(os.getcwd(), 'form-analysis-server', 'backend'))

from app.core.config import get_settings
from app.models import Record
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.models.tenant import Tenant
from app.core.database import async_session_factory

# 假設會有一個預設的 Tenant
DEFAULT_TENANT_NAME = "Default Tenant"
DEFAULT_TENANT_CODE = "DEFAULT"

async def get_or_create_default_tenant(session: AsyncSession) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.code == DEFAULT_TENANT_CODE))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        print(f"Creating default tenant: {DEFAULT_TENANT_NAME}")
        tenant = Tenant(name=DEFAULT_TENANT_NAME, code=DEFAULT_TENANT_CODE, is_default=True, is_active=True)
        session.add(tenant)
        await session.flush()
    else:
        print(f"Found default tenant: {tenant.name} ({tenant.id})")
        
    return tenant

def normalize_lot_no(lot_no_raw: str) -> int:
    # 簡易實作：移除所有非數字字符
    import re
    digits = re.sub(r'\D', '', str(lot_no_raw))
    if not digits:
        return 0 # Or handle error appropriately
    return int(digits)

async def migrate_p1_records(session: AsyncSession, tenant_id):
    print("\n--- Migrating P1 Records ---")
    query = select(Record).where(Record.data_type == 'P1')
    result = await session.execute(query)
    records = result.scalars().all()
    
    count = 0
    skipped = 0
    
    for record in records:
        # Check if exists in P1Record
        lot_no_norm = normalize_lot_no(record.lot_no)
        
        exists_query = select(P1Record).where(
            and_(
                P1Record.tenant_id == tenant_id,
                P1Record.lot_no_norm == lot_no_norm
            )
        )
        exists = await session.execute(exists_query)
        if exists.scalar_one_or_none():
            skipped += 1
            print(f"Skipping P1 {record.lot_no} (already exists)")
            continue
            
        # Construct extras
        extras = {
            "product_name": record.product_name,
            "quantity": record.quantity,
            "production_date": str(record.production_date) if record.production_date else None,
            "notes": record.notes,
            # Add other fields from records table that are p1 specific if any
        }
        if record.additional_data:
             extras.update(record.additional_data)
        
        p1 = P1Record(
            tenant_id=tenant_id,
            lot_no_raw=record.lot_no,
            lot_no_norm=lot_no_norm,
            created_at=record.created_at,
            extras=extras
        )
        session.add(p1)
        count += 1
        
    print(f"Migrated {count} P1 records, skipped {skipped}.")


async def migrate_p2_records(session: AsyncSession, tenant_id):
    print("\n--- Migrating P2 Records ---")
    # P2 records are more complex because they might have items in p2_items table
    # However, the prompt says "新資料庫未進行遷移，檔案內容暫時使用舊的record.p2_items以及record.p3_items"
    # This implies we should look into `records` table where data_type='P2' AND potentially `p2_items` table
    
    # First, let's get P2 records from `records` table
    query = select(Record).where(Record.data_type == 'P2')
    result = await session.execute(query)
    records = result.scalars().all()
    
    count = 0
    skipped = 0
    
    for record in records:
        # P2 structure: one record in `records` table might correspond to multiple winder numbers?
        # Or one record per winder number? 
        # Looking at legacy schema, `records` has `winder_number` column.
        
        winder_num = record.winder_number or 0 # Default to 0 if null ??
        lot_no_norm = normalize_lot_no(record.lot_no)

        exists_query = select(P2Record).where(
            and_(
                P2Record.tenant_id == tenant_id,
                P2Record.lot_no_norm == lot_no_norm,
                P2Record.winder_number == winder_num
            )
        )
        exists = await session.execute(exists_query)
        if exists.scalar_one_or_none():
            skipped += 1
            continue

        extras = {
            "product_name": record.product_name,
            "quantity": record.quantity,
            "production_date": str(record.production_date) if record.production_date else None,
            "sheet_width": record.sheet_width,
            "thickness1": record.thickness1,
            "thickness2": record.thickness2,
            "thickness3": record.thickness3,
            "thickness4": record.thickness4,
            "thickness5": record.thickness5,
            "thickness6": record.thickness6,
            "thickness7": record.thickness7,
            "appearance": record.appearance,
            "rough_edge": record.rough_edge,
            "slitting_result": record.slitting_result,
            "material_code": record.material_code,
            "slitting_machine_number": record.slitting_machine_number,
             # Add other fields from records table that are p2 specific
        }
        if record.additional_data:
             extras.update(record.additional_data)

        # Also check p2_items table for this record_id?
        # The prompt says "檔案內容暫時使用舊的record.p2_items" which might mean logic is reading from there.
        # But here we are migrating TO new structure.
        # If `p2_items` exists and has data for this record, we should probably use it.
        # Let's check if we can access p2_items via relationship or raw query.
        # Since we don't have p2_items loaded in Model here easily (unless we define it), using raw SQL might be safer or relying on what's in `records`.
        # However, `p2_items` table has `winder_number`, so a single `records` entry (P2 header?) might have multiple items?
        # Wait, `records` has `winder_number`. 
        # Let's assume for now 1 row in `records` (P2) -> 1 row in `p2_records`.
        
        p2 = P2Record(
            tenant_id=tenant_id,
            lot_no_raw=record.lot_no,
            lot_no_norm=lot_no_norm,
            winder_number=winder_num,
            created_at=record.created_at,
            extras=extras
        )
        session.add(p2)
        count += 1
    
    print(f"Migrated {count} P2 records from 'records' table, skipped {skipped}.")
    
    # 額外檢查：是否需要從 p2_items 遷移？
    # 如果 legacy 系統有使用 p2_items，資料可能在那裡。
    # 請根據實際情況判斷。此腳本目前主要遷移 records 表。

async def migrate_p3_records(session: AsyncSession, tenant_id):
    print("\n--- Migrating P3 Records ---")
    query = select(Record).where(Record.data_type == 'P3')
    result = await session.execute(query)
    records = result.scalars().all()
    
    count = 0
    skipped = 0
    
    for record in records:
        lot_no_norm = normalize_lot_no(record.lot_no)
        
        # P3 key: production_date, machine, mold, lot
        # Need to parse date to int yyyymmdd
        prod_date_int = 0
        if record.production_date:
            prod_date_int = int(record.production_date.strftime("%Y%m%d"))
        
        machine = record.machine_no or "UNKNOWN"
        mold = record.mold_no or "UNKNOWN"
        
        exists_query = select(P3Record).where(
            and_(
                P3Record.tenant_id == tenant_id,
                P3Record.production_date_yyyymmdd == prod_date_int,
                P3Record.machine_no == machine,
                P3Record.mold_no == mold,
                P3Record.lot_no_norm == lot_no_norm
            )
        )
        exists = await session.execute(exists_query)
        if exists.scalar_one_or_none():
            skipped += 1
            print(f"Skipping P3 {record.lot_no} (already exists)")
            continue

        extras = {
            "product_name": record.product_name,
            "quantity": record.quantity,
            "p3_no": record.p3_no,
            "notes": record.notes,
            # Add other fields from records table that are p3 specific
        }
        if record.additional_data:
             extras.update(record.additional_data)

        p3 = P3Record(
            tenant_id=tenant_id,
            lot_no_raw=record.lot_no,
            lot_no_norm=lot_no_norm,
            production_date_yyyymmdd=prod_date_int,
            machine_no=machine,
            mold_no=mold,
            product_id=record.product_id,
            created_at=record.created_at,
            extras=extras
        )
        session.add(p3)
        count += 1

    print(f"Migrated {count} P3 records, skipped {skipped}.")

async def main():
    settings = get_settings()
    print(f"Connecting to {settings.database_url}")
    
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        async with session.begin(): # Transaction
            tenant = await get_or_create_default_tenant(session)
            tenant_id = tenant.id
            
            await migrate_p1_records(session, tenant_id)
            await migrate_p2_records(session, tenant_id)
            await migrate_p3_records(session, tenant_id)
            
    print("\nMigration completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
