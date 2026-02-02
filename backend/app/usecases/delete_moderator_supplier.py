"""Use case for deleting a moderator supplier."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import ModeratorSupplierRepository


async def execute(db: AsyncSession, supplier_id: int):
    """Delete moderator supplier."""
    repo = ModeratorSupplierRepository(db)
    return await repo.delete(supplier_id)

