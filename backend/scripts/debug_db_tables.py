import asyncio
import logging
from sqlalchemy import text
from app.adapters.db.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def list_tables():
    async with AsyncSessionLocal() as db:
        try:
            # List all tables in public schema
            query = text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            result = await db.execute(query)
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"Tables in DB: {tables}")
            
            # Check specifically for 'supplier' or 'suppliers'
            if 'suppliers' in tables:
                logger.info("Table 'suppliers' found.")
            elif 'supplier' in tables:
                logger.info("Table 'supplier' found.")
            else:
                logger.warning("Neither 'suppliers' nor 'supplier' table found.")

        except Exception as e:
            logger.error(f"Error listing tables: {e}")

if __name__ == "__main__":
    asyncio.run(list_tables())
