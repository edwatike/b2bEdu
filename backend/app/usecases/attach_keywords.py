"""Use case for attaching keywords to supplier."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import KeywordRepository


async def execute(
    db: AsyncSession,
    supplier_id: int,
    keyword_id: int,
    url_count: int = 1,
    parsing_run_id: Optional[str] = None,
    first_url: Optional[str] = None
):
    """Attach keyword to supplier."""
    repo = KeywordRepository(db)
    return await repo.attach_to_supplier(
        supplier_id=supplier_id,
        keyword_id=keyword_id,
        url_count=url_count,
        parsing_run_id=parsing_run_id,
        first_url=first_url
    )

