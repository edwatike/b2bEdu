"""Use case for creating a keyword."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import KeywordRepository


async def execute(db: AsyncSession, keyword: str):
    """Create a new keyword."""
    repo = KeywordRepository(db)
    # Check if keyword already exists
    existing = await repo.get_by_keyword(keyword)
    if existing:
        return existing
    return await repo.create(keyword)

