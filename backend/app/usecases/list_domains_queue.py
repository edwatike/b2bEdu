"""Use case for listing domains queue."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import DomainQueueRepository


async def execute(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    parsing_run_id: Optional[str] = None
):
    """List domains queue entries with pagination."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"list_domains_queue.execute called with parsing_run_id={parsing_run_id}, keyword={keyword}")
    
    repo = DomainQueueRepository(db)
    entries, total = await repo.list(
        limit=limit,
        offset=offset,
        status=status,
        keyword=keyword,
        parsing_run_id=parsing_run_id
    )
    
    logger.info(f"list_domains_queue.execute returning {len(entries)} entries, total={total}")
    return entries, total

