import asyncio
import os
import sys
from datetime import date
from typing import Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 添加 backend 到 sys.path
print("Starting migration script...", flush=True)
sys.path.insert(0, os.path.join(os.getcwd(), 'app')) # in container, /app is the root of code

from app.core.config import get_settings
from app.models import Record
from app.models.p1_record import P1Record
from app.models.p2_record import P2Record
from app.models.p3_record import P3Record
from app.models.core.tenant import Tenant
from app.models.p2_item import P2Item
from app.models.p3_item import P3Item
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
    if not lot_no_raw:
        return 0
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
            # print(f"Skipping P1 {record.lot_no} (already exists)")
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
    query = select(Record).where(Record.data_type == 'P2')
    result = await session.execute(query)
    records = result.scalars().all()
    
    count = 0
    skipped = 0
    
    # Existing behavior: Migrating from 'records' table (headers)
    for record in records:
        # Check if this record has associated p2_items
        # In V1: Record was header, P2Item was row.
        # In V2: P2Record IS the row.  
        # So we should migrate from P2Item connected to this record, NOT just the Record itself.
        
        # Load p2 items for this record
        items_query = select(P2Item).where(P2Item.record_id == record.id)
        items_result = await session.execute(items_query)
        items = items_result.scalars().all()

        if not items:
            # Fallback for old data or if somehow items don't exist but record does (should not happen in normalized P2)
            # Or if this migration script logic was assuming Record was enough.
            print(f"Warning: Record {record.id} (Lot: {record.lot_no}) has no P2Items. Skipping or migrating as single header?")
            # Original logic was here. But user says "P2_records only 1, but P2_items has 20".
            # This confirms we need to migrate items -> P2Record rows.
            continue
        
        print(f"Record {record.id} has {len(items)} items. Migrating items to P2Records...")

        for item in items:
             winder_num = item.winder_number or 0 # Use item's winder number
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
                "quantity": record.quantity, # Header info duplicated to row
                "production_date": str(record.production_date) if record.production_date else None,
                "material_code": record.material_code,
                "slitting_machine_number": record.slitting_machine_number,
                
                # Item specific fields
                "sheet_width": item.sheet_width,
                "thickness1": item.thickness1,
                "thickness2": item.thickness2,
                "thickness3": item.thickness3,
                "thickness4": item.thickness4,
                "thickness5": item.thickness5,
                "thickness6": item.thickness6,
                "thickness7": item.thickness7,
                "appearance": item.appearance,
                "rough_edge": item.rough_edge,
                "slitting_result": item.slitting_result,
             }
             if record.additional_data:
                  extras.update(record.additional_data)

             p2 = P2Record(
                tenant_id=tenant_id,
                lot_no_raw=record.lot_no,
                lot_no_norm=lot_no_norm,
                winder_number=winder_num,
                extras=extras 
             )
             session.add(p2)
             count += 1
             
    print(f"Migrated {count} P2 records (from items), skipped {skipped}.")

async def migrate_p3_records(session: AsyncSession, tenant_id):
    print("\n--- Migrating P3 Records ---")
    
    # We need to start a NEW transaction/query because the previous one was committed? 
    # Actually async session should handle it if we are careful.
    # The error 'Can't operate on closed transaction' suggests something went wrong in main loop or session handling.
    # But usually session stays open. Likely the loop or context manager usage.
    
    query = select(Record).where(Record.data_type == 'P3')
    result = await session.execute(query)
    records = result.scalars().all()
    
    count = 0
    skipped = 0
    
    for record in records:
        lot_no_norm = normalize_lot_no(record.lot_no)
        
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
                # P3Record.lot_no_norm == lot_no_norm # 暫不檢查 lot_no_norm，因為 P3 composite unique key 可能包含它，但也可能同一 batch 有多個 lot? 
                # IMPLEMENTATION_PLAN says P3 unique is: tenant, date, machine, mold, lot. So we should check lot.
                P3Record.lot_no_norm == lot_no_norm
            )
        )
        exists = await session.execute(exists_query)
        if exists.scalar_one_or_none():
            skipped += 1
            # print(f"Skipping P3 {record.lot_no} (already exists)")
            continue

        extras = {
            "product_name": record.product_name,
            "quantity": record.quantity,
            "p3_no": record.p3_no,
            "notes": record.notes,
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
    print(f"Connecting to DB...")
    
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
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
