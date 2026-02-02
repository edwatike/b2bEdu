"""Use case for getting a moderator supplier."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import ModeratorSupplierRepository


async def execute(db: AsyncSession, supplier_id: int):
    """Get moderator supplier by ID."""
    repo = ModeratorSupplierRepository(db)
    return await repo.get_by_id(supplier_id)

