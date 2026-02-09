"""Use case for removing domain from blacklist."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import BlacklistRepository


async def execute(db: AsyncSession, domain: str):
    """Remove domain from blacklist."""
    repo = BlacklistRepository(db)
    return await repo.delete(domain)

