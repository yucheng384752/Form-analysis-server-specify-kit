import sys
import os
import asyncio
from sqlalchemy import text, func, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Determine the absolute path to the backend directory
script_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.dirname(script_dir)
backend_dir = os.path.join(workspace_root, 'form-analysis-server', 'backend')

if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Hardcode the URL for debugging/script usage
DATABASE_URL = "postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db"

from app.models.record import Record
from app.models.p2_item import P2Item
from app.models.p3_item import P3Item

async def cleanup_duplicates():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        print("Scanning for duplicate records...")
        
        # Find lot_nos that have more than 1 record
        # We group by lot_no and count
        stmt = (
            select(Record.lot_no, func.count(Record.id).label('count'))
            .group_by(Record.lot_no)
            .having(func.count(Record.id) > 1)
        )
        
        result = await db.execute(stmt)
        duplicates = result.fetchall()
        
        if not duplicates:
            print(" No duplicate records found.")
            return

        print(f"Found {len(duplicates)} lots with duplicate records.")
        
        deleted_count = 0
        
        for lot_no, count in duplicates:
            print(f"\nProcessing Lot: {lot_no} (Count: {count})")
            
            # Get all records for this lot
            records_stmt = (
                select(Record)
                .where(Record.lot_no == lot_no)
                .order_by(Record.created_at.desc()) # Newest first
            )
            result_records = await db.execute(records_stmt)
            records = result_records.scalars().all()
            
            # Analyze each record
            record_stats = []
            for r in records:
                # Count P2 items
                p2_count_stmt = select(func.count(P2Item.id)).where(P2Item.record_id == r.id)
                p2_count = (await db.execute(p2_count_stmt)).scalar()
                
                record_stats.append({
                    'id': r.id,
                    'created_at': r.created_at,
                    'p2_items_count': p2_count,
                    'record_obj': r
                })
                print(f"   - ID: {r.id}, Created: {r.created_at}, P2 Items: {p2_count}")
            
            # Strategy: Keep the one with the most P2 items. If tie, keep the newest.
            # Sort by p2_items_count (desc), then created_at (desc)
            record_stats.sort(key=lambda x: (x['p2_items_count'], x['created_at']), reverse=True)
            
            winner = record_stats[0]
            losers = record_stats[1:]
            
            print(f"    Keeping: {winner['id']} (Items: {winner['p2_items_count']})")
            
            for loser in losers:
                print(f"   🗑️ Deleting: {loser['id']} (Items: {loser['p2_items_count']})")
                await db.delete(loser['record_obj'])
                deleted_count += 1
        
        if deleted_count > 0:
            print(f"\n💾 Committing changes... Deleted {deleted_count} records.")
            await db.commit()
        else:
            print("\nNo records deleted.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(cleanup_duplicates())
