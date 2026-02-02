"""Use case for getting supplier keywords."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import ModeratorSupplierRepository


async def execute(db: AsyncSession, supplier_id: int):
    """Get supplier keywords."""
    repo = ModeratorSupplierRepository(db)
    return await repo.get_keywords(supplier_id)

