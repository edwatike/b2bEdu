"""Use case for removing domain from queue."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import DomainQueueRepository


async def execute(db: AsyncSession, domain: str):
    """Remove domain from queue."""
    repo = DomainQueueRepository(db)
    return await repo.delete(domain)

