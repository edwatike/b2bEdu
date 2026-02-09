"""Router for parsing operations."""
from fastapi import APIRouter, Depends, BackgroundTasks, Body, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any

from app.adapters.db.session import get_db
from app.transport.routers.auth import get_current_user
from app.utils.authz import require_moderator
from app.utils.rate_limit import limiter, PARSING_START_LIMIT
from app.transport.schemas.parsing import (
    StartParsingRequestDTO,
    ParsingStatusResponseDTO
)
from app.usecases import (
    start_parsing,
    get_parsing_status
)

router = APIRouter()


@router.post("/start", status_code=201)
@limiter.limit(PARSING_START_LIMIT)
async def start_parsing_endpoint(
    request: Request,
    body: StartParsingRequestDTO,
    background_tasks: BackgroundTasks,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Start parsing for a keyword."""
    require_moderator(current_user)
    # Validate source
    valid_sources = ["google", "yandex", "both"]
    source = body.source.lower() if body.source else "google"
    if source not in valid_sources:
        source = "google"
    
    result = await start_parsing.execute(
        db=db,
        keyword=body.keyword,
        depth=body.depth,
        source=source,
        background_tasks=background_tasks
    )

    # Ensure moderator_task exists for this request so current-task block works
    request_id = result.get("request_id")
    if request_id:
        from sqlalchemy import text
        try:
            existing = await db.execute(
                text("SELECT id FROM moderator_tasks WHERE request_id = :rid LIMIT 1"),
                {"rid": int(request_id)},
            )
            if not existing.fetchone():
                user_id = int(current_user.get("id", 0))
                await db.execute(
                    text(
                        "INSERT INTO moderator_tasks (request_id, created_by, title, status, source, depth) "
                        "VALUES (:request_id, :created_by, :title, :status, :source, :depth)"
                    ),
                    {
                        "request_id": int(request_id),
                        "created_by": user_id,
                        "title": body.keyword,
                        "status": "running",
                        "source": source,
                        "depth": body.depth,
                    },
                )
        except Exception:
            pass

    await db.commit()
    
    # Return response with camelCase field names for frontend
    # Using JSONResponse directly to bypass any FastAPI response validation
    return JSONResponse(
        status_code=201,
        content={
            "runId": result["run_id"],
            "keyword": result["keyword"],
            "status": result["status"]
        }
    )


@router.put("/status/{run_id}")
async def update_parsing_status_endpoint(
    run_id: str,
    request_data: Dict[str, Any] = Body(default={}),
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update parsing run status (for CAPTCHA and progress updates)."""
    require_moderator(current_user)
    from app.adapters.db.repositories import ParsingRunRepository
    
    run_repo = ParsingRunRepository(db)
    update_data = {}
    
    # Получаем error_message из тела запроса
    if request_data and "error_message" in request_data:
        update_data["error_message"] = request_data["error_message"]
    
    if update_data:
        await run_repo.update(run_id, update_data)
        await db.commit()
    
    return {"status": "updated"}


@router.get("/status/{run_id}", response_model=ParsingStatusResponseDTO)
async def get_parsing_status_endpoint(
    run_id: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get parsing status by run ID."""
    require_moderator(current_user)
    import json
    import logging
    from fastapi import HTTPException
    
    logger = logging.getLogger(__name__)
    
    run = await get_parsing_status.execute(db=db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Parsing run not found")
    
    try:
        # Extract keyword from request.title or raw_keys_json
        keyword = "Unknown"
        if run.request:
            if run.request.title:
                keyword = run.request.title
            elif run.request.raw_keys_json:
                try:
                    keys_data = json.loads(run.request.raw_keys_json)
                    if isinstance(keys_data, list) and len(keys_data) > 0:
                        keyword = keys_data[0] if isinstance(keys_data[0], str) else str(keys_data[0])
                    elif isinstance(keys_data, dict) and "keys" in keys_data:
                        keys = keys_data["keys"]
                        if isinstance(keys, list) and len(keys) > 0:
                            keyword = keys[0] if isinstance(keys[0], str) else str(keys[0])
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass
        
        # Create DTO with extracted keyword
        # Используем camelCase для соответствия DTO
        # CRITICAL FIX: Use getattr() for safe access to SimpleNamespace attributes
        from app.adapters.db.repositories import DomainQueueRepository
        domain_queue_repo = DomainQueueRepository(db)
        _, count = await domain_queue_repo.list(
            limit=1,
            offset=0,
            parsing_run_id=run_id
        )
        results_count = count if count > 0 else None
        
        # CRITICAL FIX: Use getattr() for safe access to SimpleNamespace attributes
        # Pydantic v2 with alias requires the field name (run_id), not the alias (runId)
        run_id_value = getattr(run, 'run_id', None)
        status_value = getattr(run, 'status', None)
        started_at_value = getattr(run, 'started_at', None)
        finished_at_value = getattr(run, 'finished_at', None)
        error_message_value = getattr(run, 'error_message', None)
        
        status_dict = {
            "run_id": run_id_value,  # Use field name, not alias
            "keyword": keyword,
            "status": status_value,
            "started_at": started_at_value,  # Use field name, not alias
            "finished_at": finished_at_value,  # Use field name, not alias
            "error_message": error_message_value,  # Use field name, not alias
            "resultsCount": results_count,  # No alias, use camelCase
        }
        return ParsingStatusResponseDTO.model_validate(status_dict)
    except Exception as e:
        logger.error(f"Error converting parsing status {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing parsing status: {str(e)}")



