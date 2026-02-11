import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def check_domain_logs():
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'domain_logs'
            )
        """))
        table_exists = result.scalar()
        print(f"Table domain_logs exists: {table_exists}")
        
        if not table_exists:
            print("Creating domain_logs table...")
            await conn.execute(text("""
                CREATE TABLE domain_logs (
                    id SERIAL PRIMARY KEY,
                    domain VARCHAR(255) NOT NULL,
                    run_id VARCHAR(255),
                    action VARCHAR(100) NOT NULL,
                    message TEXT,
                    details JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX idx_domain_logs_domain ON domain_logs (domain)"))
            await conn.execute(text("CREATE INDEX idx_domain_logs_run_id ON domain_logs (run_id)"))
            await conn.execute(text("CREATE INDEX idx_domain_logs_created_at ON domain_logs (created_at DESC)"))
            await conn.commit()
            print("Table created successfully")
    
    # Start new transaction for queries
    async with engine.begin() as conn:
        # Check total records
        result = await conn.execute(text("SELECT COUNT(*) FROM domain_logs"))
        total = result.scalar()
        print(f"Total records in domain_logs: {total}")
        
        # Search for rzhevka-market.ru
        result = await conn.execute(text("""
            SELECT id, domain, run_id, action, message, created_at 
            FROM domain_logs 
            WHERE domain = :domain 
            ORDER BY created_at DESC 
            LIMIT 5
        """), {"domain": "rzhevka-market.ru"})
        
        rows = result.fetchall()
        print(f"\nRecords for rzhevka-market.ru: {len(rows)}")
        for row in rows:
            print(f"  ID: {row[0]}, Run: {row[2]}, Action: {row[3]}, Message: {row[4]}, Date: {row[5]}")
        
        # Show recent records for debugging
        result = await conn.execute(text("""
            SELECT domain, action, COUNT(*) as cnt 
            FROM domain_logs 
            GROUP BY domain, action 
            ORDER BY cnt DESC 
            LIMIT 10
        """))
        
        recent = result.fetchall()
        print(f"\nTop domains by action count:")
        for row in recent:
            print(f"  {row[0]}: {row[1]} ({row[2]} records)")

if __name__ == "__main__":
    asyncio.run(check_domain_logs())
