"""Use case for deleting a keyword."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import KeywordRepository


async def execute(db: AsyncSession, keyword_id: int):
    """Delete keyword."""
    repo = KeywordRepository(db)
    return await repo.delete(keyword_id)

