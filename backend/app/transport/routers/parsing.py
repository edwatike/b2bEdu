"""Router for parsing operations."""
import os
from pathlib import Path
import json
from fastapi import APIRouter, Depends, BackgroundTasks, Body, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any

from app.adapters.db.session import get_db
from app.transport.schemas.parsing import (
    StartParsingRequestDTO,
    ParsingStatusResponseDTO
)
from app.usecases import (
    start_parsing,
    get_parsing_status
)


def _agent_debug_log(payload: dict) -> None:
    if os.environ.get("AGENT_DEBUG_LOG", "0") != "1":
        return
    try:
        project_root = Path(__file__).resolve().parents[4]
        out_dir = project_root / ".cursor"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "debug.log"
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return

router = APIRouter()


@router.post("/start", status_code=201)
async def start_parsing_endpoint(
    request: StartParsingRequestDTO,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
):
    """Start parsing for a keyword."""
    from datetime import datetime
    _agent_debug_log({
        "location": "parsing.py:20",
        "message": "start_parsing_endpoint called",
        "data": {
            "keyword": request.keyword,
            "depth": request.depth,
            "source": request.source,
            "has_background_tasks": background_tasks is not None,
        },
        "timestamp": int(datetime.utcnow().timestamp() * 1000),
        "sessionId": "debug-session",
        "runId": "",
        "hypothesisId": "A",
    })
    # Validate source
    valid_sources = ["google", "yandex", "both"]
    source = request.source.lower() if request.source else "google"
    if source not in valid_sources:
        source = "google"
    
    result = await start_parsing.execute(
        db=db,
        keyword=request.keyword,
        depth=request.depth,
        source=source,
        background_tasks=background_tasks
    )
    _agent_debug_log({
        "location": "parsing.py:40",
        "message": "start_parsing.execute returned",
        "data": {"run_id": result.get("run_id"), "status": result.get("status")},
        "timestamp": int(datetime.utcnow().timestamp() * 1000),
        "sessionId": "debug-session",
        "runId": result.get("run_id", ""),
        "hypothesisId": "A",
    })
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
    db = Depends(get_db)
):
    """Update parsing run status (for CAPTCHA and progress updates)."""
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
    db = Depends(get_db)
):
    """Get parsing status by run ID."""
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



