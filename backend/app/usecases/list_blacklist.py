"""Use case for listing blacklist entries."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import BlacklistRepository


async def execute(db: AsyncSession, limit: int = 100, offset: int = 0):
    """List blacklist entries with pagination."""
    repo = BlacklistRepository(db)
    return await repo.list(limit=limit, offset=offset)

