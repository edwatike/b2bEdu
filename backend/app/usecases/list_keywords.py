"""Use case for listing keywords."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import KeywordRepository


async def execute(db: AsyncSession):
    """List all keywords."""
    repo = KeywordRepository(db)
    return await repo.list()

