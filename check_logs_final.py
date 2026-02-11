import asyncio
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def check_logs():
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT id, domain, action, message, run_id, created_at 
            FROM domain_logs 
            WHERE domain = 'rzhevka-market.ru' 
            ORDER BY created_at DESC 
            LIMIT 10
        """))
        
        rows = result.fetchall()
        print(f'Domain logs for rzhevka-market.ru: {len(rows)}')
        for row in rows:
            print(f'  ID: {row[0]}, Action: {row[2]}, Message: {row[3]}, Run: {row[4]}, Date: {row[5]}')

if __name__ == "__main__":
    asyncio.run(check_logs())
