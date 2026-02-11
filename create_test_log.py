import asyncio
import sys, os, json
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def create_test_logs():
    """Create test log entries for rzhevka-market.ru to simulate parsing history."""
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        # Insert test log entries
        test_logs = [
            ("rzhevka-market.ru", "processing", "Начало обработки домена", "435e6e2f-00d8-4651-b359-e0d3936f487f", {"stage": "start"}),
            ("rzhevka-market.ru", "requires_moderation", "Требуется модерация", "435e6e2f-00d8-4651-b359-e0d3936f487f", {"reason": "missing_inn_or_email"}),
        ]
        
        for domain, action, message, run_id, details in test_logs:
            await conn.execute(text("""
                INSERT INTO domain_logs (domain, run_id, action, message, details)
                VALUES (:domain, :run_id, :action, :message, :details)
            """), {
                "domain": domain,
                "run_id": run_id,
                "action": action,
                "message": message,
                "details": json.dumps(details),
            })
        
        print(f"Created {len(test_logs)} test log entries")
        
        # Verify
        result = await conn.execute(text("""
            SELECT id, action, message, run_id, created_at 
            FROM domain_logs 
            WHERE domain = 'rzhevka-market.ru' 
            ORDER BY created_at DESC
        """))
        
        rows = result.fetchall()
        print(f"\nTotal logs for rzhevka-market.ru: {len(rows)}")
        for row in rows:
            print(f"  ID: {row[0]}, Action: {row[1]}, Message: {row[2]}, Run: {row[3]}, Date: {row[4]}")

if __name__ == "__main__":
    asyncio.run(create_test_logs())
