import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def check_run_domains():
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        # Check if run_domains table exists
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'run_domains'
            )
        """))
        table_exists = result.scalar()
        print(f"Table run_domains exists: {table_exists}")
        
        if not table_exists:
            print("run_domains table doesn't exist")
            return
        
        # Search for rzhevka-market.ru in run_domains
        result = await conn.execute(text("""
            SELECT run_id, domain, status, reason, created_at, updated_at 
            FROM run_domains 
            WHERE domain = :domain 
            ORDER BY created_at DESC 
            LIMIT 10
        """), {"domain": "rzhevka-market.ru"})
        
        rows = result.fetchall()
        print(f"\nRecords in run_domains for rzhevka-market.ru: {len(rows)}")
        for row in rows:
            print(f"  Run: {row[0]}, Status: {row[2]}, Reason: {row[3][:100] if row[3] else None}, Created: {row[4]}, Updated: {row[5]}")
        
        # Check similar domains (maybe with different normalization)
        result = await conn.execute(text("""
            SELECT run_id, domain, status, created_at 
            FROM run_domains 
            WHERE domain ILIKE '%rzhevka%' OR domain ILIKE '%market%'
            ORDER BY created_at DESC 
            LIMIT 10
        """))
        
        rows = result.fetchall()
        print(f"\nRecords with 'rzhevka' or 'market' in domain: {len(rows)}")
        for row in rows:
            print(f"  Run: {row[0]}, Domain: {row[1]}, Status: {row[2]}, Created: {row[3]}")
        
        # Check total parsing runs
        result = await conn.execute(text("SELECT COUNT(*) FROM parsing_runs"))
        total_runs = result.scalar()
        print(f"\nTotal parsing runs: {total_runs}")
        
        # Show recent runs
        result = await conn.execute(text("""
            SELECT id, run_id, created_at, status 
            FROM parsing_runs 
            ORDER BY created_at DESC 
            LIMIT 5
        """))
        
        runs = result.fetchall()
        print(f"\nRecent parsing runs:")
        for run in runs:
            print(f"  ID: {run[0]}, Run: {run[1]}, Date: {run[2]}, Status: {run[3]}")

if __name__ == "__main__":
    asyncio.run(check_run_domains())
