"""Router for blacklist."""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.adapters.db.session import get_db
from app.transport.routers.auth import can_access_moderator_zone, get_current_user
from app.config import settings
from app.transport.schemas.blacklist import (
    BlacklistEntryDTO,
    AddToBlacklistRequestDTO,
    BlacklistResponseDTO,
)
from app.usecases import (
    add_to_blacklist,
    list_blacklist,
    remove_from_blacklist,
)

router = APIRouter()


def _require_moderator(current_user: dict):
    if not can_access_moderator_zone(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

def _require_debug():
    if str(getattr(settings, "ENV", "")).lower() != "development":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.get("/blacklist-debug", tags=["Debug"])
async def debug_blacklist_endpoint(
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Debug endpoint to check blacklist data directly from database."""
    _require_moderator(current_user)
    _require_debug()
    from app.adapters.db.repositories import BlacklistRepository
    
    repo = BlacklistRepository(db)
    
    # Получаем данные напрямую
    entries, total = await repo.list(limit=100, offset=0)
    
    return {
        "total": total,
        "entries_count": len(entries),
        "entries": [
            {
                "domain": e.domain,
                "reason": e.reason,
                "added_at": e.added_at.isoformat() if e.added_at else None,
                "added_by": e.added_by
            }
            for e in entries
        ]
    }


@router.get("/blacklist", response_model=BlacklistResponseDTO)
async def list_blacklist_endpoint(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List blacklist entries with pagination."""
    _require_moderator(current_user)
    import logging
    logger = logging.getLogger(__name__)
    
    entries, total = await list_blacklist.execute(
        db=db,
        limit=limit,
        offset=offset
    )
    
    logger.info(f"Blacklist query: found {total} total entries, returning {len(entries)} entries")
    
    # Конвертируем entries в DTO, обрабатывая datetime
    entry_dtos = []
    for e in entries:
        try:
            entry_dict = {
                "domain": e.domain,
                "reason": e.reason,
                "added_by": e.added_by,
                "added_at": e.added_at.isoformat() if e.added_at else None,  # Конвертируем datetime в строку
                "parsing_run_id": e.parsing_run_id,
            }
            entry_dto = BlacklistEntryDTO.model_validate(entry_dict)
            entry_dtos.append(entry_dto)
            logger.debug(f"Converted entry: {e.domain}")
        except Exception as ex:
            logger.error(f"Error converting entry {e.domain}: {ex}")
            # Пропускаем проблемную запись, но продолжаем обработку остальных
            continue
    
    logger.info(f"Returning {len(entry_dtos)} DTOs")
    
    return BlacklistResponseDTO(
        entries=entry_dtos,
        total=total,
        limit=limit,
        offset=offset
    )


@router.post("/blacklist", response_model=BlacklistEntryDTO, status_code=201)
async def add_to_blacklist_endpoint(
    request: AddToBlacklistRequestDTO,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add domain to blacklist."""
    _require_moderator(current_user)
    import logging
    logger = logging.getLogger(__name__)
    
    # Валидация данных через Pydantic (уже выполнена, но добавим дополнительную проверку)
    blacklist_data = request.model_dump()
    domain = blacklist_data.get("domain", "unknown")
    
    # Дополнительная валидация на уровне endpoint
    if not domain or len(domain.strip()) < 3:
        logger.error(f"Invalid domain format: {domain}")
        raise HTTPException(status_code=400, detail="Invalid domain format")
    
    logger.info(f"Adding domain to blacklist: {domain}")
    
    # Convert camelCase to snake_case
    if "addedBy" in blacklist_data:
        blacklist_data["added_by"] = blacklist_data.pop("addedBy")
    if "parsingRunId" in blacklist_data:
        blacklist_data["parsing_run_id"] = blacklist_data.pop("parsingRunId")
    
    try:
        entry = await add_to_blacklist.execute(db=db, blacklist_data=blacklist_data)
        
        # CRITICAL: Commit FIRST, before audit log
        # This ensures the domain is saved even if audit log fails
        await db.flush()
        await db.commit()
        logger.info(f"Successfully added domain to blacklist: {domain} (added_at: {entry.added_at})")
        
        # Log to audit_log AFTER commit (in a separate transaction)
        # This way audit log errors won't affect the blacklist entry
        try:
            from app.adapters.audit import log_audit
            from app.adapters.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as audit_session:
                await log_audit(
                    db=audit_session,
                    table_name="blacklist",
                    operation="INSERT",
                    record_id=entry.domain,
                    new_data={
                        "domain": entry.domain,
                        "reason": entry.reason,
                        "added_by": entry.added_by,
                        "parsing_run_id": entry.parsing_run_id
                    },
                    changed_by=entry.added_by or "system"
                )
                await audit_session.commit()
        except Exception as audit_err:
            logger.warning(f"Error logging audit for domain {domain}: {audit_err}")
            # Don't fail the add if audit logging fails
        
        # Конвертируем entry в DTO с правильной обработкой datetime
        entry_dict = {
            "domain": entry.domain,
            "reason": entry.reason,
            "added_by": entry.added_by,
            "added_at": entry.added_at.isoformat() if entry.added_at else None,
            "parsing_run_id": entry.parsing_run_id,
        }
        return BlacklistEntryDTO.model_validate(entry_dict)
    except Exception as e:
        logger.error(f"Error adding domain {domain} to blacklist: {e}", exc_info=True)
        await db.rollback()
        raise


@router.delete("/blacklist/{domain}", status_code=204)
async def remove_from_blacklist_endpoint(
    domain: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove domain from blacklist."""
    _require_moderator(current_user)
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Removing domain from blacklist: {domain}")
    
    try:
        success = await remove_from_blacklist.execute(db=db, domain=domain)
        if not success:
            logger.warning(f"Domain not found in blacklist: {domain}")
            raise HTTPException(status_code=404, detail="Domain not found in blacklist")
        
        await db.commit()
        logger.info(f"Successfully removed domain from blacklist: {domain}")
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error removing domain {domain} from blacklist: {e}", exc_info=True)
        await db.rollback()
        raise
