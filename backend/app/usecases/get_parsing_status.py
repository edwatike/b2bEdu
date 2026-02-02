"""Use case for getting parsing status."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import ParsingRunRepository


async def execute(db: AsyncSession, run_id: str):
    """Get parsing status by run ID."""
    repo = ParsingRunRepository(db)
    return await repo.get_by_id(run_id)

