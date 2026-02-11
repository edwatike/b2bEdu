import asyncio
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def check_schema():
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        # Get parsing_runs columns
        result = await conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'parsing_runs' 
            ORDER BY ordinal_position
        """))
        
        columns = result.fetchall()
        print('parsing_runs columns:')
        for col in columns:
            print(f'  {col[0]}: {col[1]}')

if __name__ == "__main__":
    asyncio.run(check_schema())
