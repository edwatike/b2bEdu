"""Use case for adding domain to blacklist."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import BlacklistRepository


async def execute(db: AsyncSession, blacklist_data: dict):
    """Add domain to blacklist."""
    repo = BlacklistRepository(db)
    # Check if already blacklisted
    existing = await repo.get_by_domain(blacklist_data["domain"])
    if existing:
        return existing
    return await repo.create(blacklist_data)

