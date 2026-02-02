"""Router for domains queue."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.session import get_db
from app.transport.schemas.domain import (
    DomainQueueEntryDTO,
    DomainsQueueResponseDTO,
)
from app.usecases import (
    list_domains_queue,
    remove_from_domains_queue,
)

router = APIRouter()


@router.get("/queue", response_model=DomainsQueueResponseDTO)
async def list_domains_queue_endpoint(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    parsingRunId: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    """List domains queue entries with pagination."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Валидация и нормализация параметров
    if parsingRunId:
        parsingRunId = parsingRunId.strip()
        if not parsingRunId:
            parsingRunId = None
    
    if keyword:
        keyword = keyword.strip()
        if not keyword:
            keyword = None
    
    logger.info(f"list_domains_queue_endpoint called with parsingRunId={parsingRunId}, keyword={keyword}, status={status}")
    
    # DEBUG: Log the actual parameter value
    if parsingRunId:
        logger.info(f"DEBUG: parsingRunId value: '{parsingRunId}' (type: {type(parsingRunId)}, len: {len(parsingRunId)})")
    
    entries, total = await list_domains_queue.execute(
        db=db,
        limit=limit,
        offset=offset,
        status=status,
        keyword=keyword,
        parsing_run_id=parsingRunId  # Pass parsingRunId as parsing_run_id
    )
    
    logger.info(f"list_domains_queue_endpoint returning {len(entries)} entries, total={total}")
    
    # CRITICAL FIX: Use model_validate with from_attributes=True for SQLAlchemy models
    # This properly handles all fields including parsing_run_id
    try:
        dto_entries = [
            DomainQueueEntryDTO.model_validate(entry, from_attributes=True)
            for entry in entries
        ]
    except Exception as e:
        logger.error(f"Error converting entries to DTO: {e}", exc_info=True)
        # Fallback: convert to dict manually
        entries_dicts = []
        for entry in entries:
            entry_dict = {
                "domain": entry.domain,
                "keyword": entry.keyword,
                "url": entry.url,
                "parsing_run_id": entry.parsing_run_id,
                "status": entry.status,
                "created_at": entry.created_at
            }
            entries_dicts.append(entry_dict)
        dto_entries = [DomainQueueEntryDTO.model_validate(e) for e in entries_dicts]
    
    return DomainsQueueResponseDTO(
        entries=dto_entries,
        total=total,
        limit=limit,
        offset=offset
    )


@router.delete("/queue/{domain}", status_code=204)
async def remove_from_domains_queue_endpoint(
    domain: str,
    db: AsyncSession = Depends(get_db)
):
    """Remove domain from queue."""
    success = await remove_from_domains_queue.execute(db=db, domain=domain)
    if not success:
        raise HTTPException(status_code=404, detail="Domain not found in queue")
    
    await db.commit()

