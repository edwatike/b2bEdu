import asyncio
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings
from app.transport.routers.domain_logs import write_log, ensure_table
from app.adapters.db.session import AsyncSessionLocal

async def test_log_write():
    """Test writing a log entry directly."""
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with AsyncSessionLocal() as log_db:
        await ensure_table(log_db)
        
        # Write a test log entry
        await write_log(
            log_db, 
            "rzhevka-market.ru", 
            "test_action",
            message="Test log entry",
            run_id="test-run-123",
            details={"test": True}
        )
        
        print("Test log entry written successfully")
        
        # Check if it was written
        result = await log_db.execute(text("""
            SELECT id, domain, action, message, run_id 
            FROM domain_logs 
            WHERE domain = :domain 
            ORDER BY created_at DESC 
            LIMIT 5
        """), {"domain": "rzhevka-market.ru"})
        
        rows = result.fetchall()
        print(f"\nLog entries for rzhevka-market.ru: {len(rows)}")
        for row in rows:
            print(f"  ID: {row[0]}, Action: {row[2]}, Message: {row[3]}, Run: {row[4]}")

if __name__ == "__main__":
    asyncio.run(test_log_write())
