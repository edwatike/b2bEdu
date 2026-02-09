import asyncio
import logging
from sqlalchemy import text
from app.adapters.db.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def delete_suppliers_without_inn():
    async with AsyncSessionLocal() as db:
        try:
            # Check count first
            count_query = text("SELECT count(*) FROM moderator_suppliers WHERE inn IS NULL OR inn = ''")
            result = await db.execute(count_query)
            count = result.scalar()
            logger.info(f"Found {count} suppliers without INN in moderator_suppliers.")

            if count > 0:
                delete_query = text("DELETE FROM moderator_suppliers WHERE inn IS NULL OR inn = ''")
                await db.execute(delete_query)
                await db.commit()
                logger.info(f"Successfully deleted {count} suppliers without INN.")
            else:
                logger.info("No suppliers to delete.")
                
        except Exception as e:
            logger.error(f"Error deleting suppliers: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(delete_suppliers_without_inn())
