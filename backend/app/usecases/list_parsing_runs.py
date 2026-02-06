"""Use case for listing parsing runs."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import ParsingRunRepository


async def execute(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    request_id: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc"
):
    """List parsing runs with pagination, filtering, and sorting."""
    repo = ParsingRunRepository(db)
    return await repo.list(
        limit=limit,
        offset=offset,
        status=status,
        keyword=keyword,
        request_id=request_id,
        sort_by=sort_by,
        sort_order=sort_order
    )

