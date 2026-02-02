"""Use case for listing moderator suppliers."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import ModeratorSupplierRepository


async def execute(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    type_filter: Optional[str] = None
):
    """List moderator suppliers with pagination."""
    repo = ModeratorSupplierRepository(db)
    return await repo.list(limit=limit, offset=offset, type_filter=type_filter)

