"""Router for parsing runs."""
import os
from pathlib import Path
import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.adapters.db.session import get_db
from app.transport.schemas.parsing import (
    ParsingRunDTO,
    ParsingRunsListResponseDTO,
)
from app.usecases import (
    list_parsing_runs,
    get_parsing_run,
    delete_parsing_run,
)

router = APIRouter()


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


@router.get("/runs", response_model=ParsingRunsListResponseDTO)
async def list_parsing_runs_endpoint(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    request_id: Optional[int] = Query(default=None),
    sort: Optional[str] = Query(default="created_at"),
    order: Optional[str] = Query(default="desc"),
    db = Depends(get_db)
):
    """List parsing runs with pagination, filtering, and sorting."""
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Валидация sort и order
    valid_sort_fields = ["run_id", "status", "created_at", "started_at", "finished_at"]
    if sort not in valid_sort_fields:
        sort = "created_at"
    
    if order not in ["asc", "desc"]:
        order = "desc"
    
    runs, total = await list_parsing_runs.execute(
        db=db,
        limit=limit,
        offset=offset,
        status=status,
        keyword=keyword,
        request_id=request_id,
        sort_by=sort,
        sort_order=order
    )
    
    # Convert runs to DTOs, extracting keyword from process_log/raw_keys_json/title
    run_dtos = []
    for run in runs:
        try:
            keyword = "Unknown"

            # 1) Prefer process_log keyword (this is the actual key used for this run)
            try:
                pl = getattr(run, "process_log", None)
                if isinstance(pl, dict):
                    k0 = pl.get("keyword")
                    if isinstance(k0, str) and k0.strip():
                        keyword = k0.strip()
            except Exception:
                pass

            # 2) Fallback: use first key from request.raw_keys_json (if keyword still unknown)
            if keyword == "Unknown" and getattr(run, "request", None) and getattr(run.request, "raw_keys_json", None):
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

            # 3) Last fallback: request title
            if keyword == "Unknown" and getattr(run, "request", None) and getattr(run.request, "title", None):
                if run.request.title:
                    keyword = run.request.title
            
            # CRITICAL FIX: Always calculate results_count from domains_queue
            # This completely avoids AttributeError by never accessing the model attribute
            from app.adapters.db.repositories import DomainQueueRepository
            domain_queue_repo = DomainQueueRepository(db)
            try:
                _, count = await domain_queue_repo.list(
                    limit=1,
                    offset=0,
                    parsing_run_id=run.run_id
                )
                results_count = count if count > 0 else None
            except Exception:
                results_count = None
            
            # Create DTO with extracted keyword
            run_dict = {
                "runId": run.run_id,
                "keyword": keyword,
                "status": run.status,
                "startedAt": run.started_at.isoformat() if run.started_at else None,
                "finishedAt": run.finished_at.isoformat() if run.finished_at else None,
                "error": run.error_message,
                "resultsCount": results_count,
                "createdAt": run.created_at.isoformat() if run.created_at else None,
                "depth": run.depth,
            }
            run_dto = ParsingRunDTO.model_validate(run_dict)
            run_dtos.append(run_dto)
        except Exception as e:
            logger.error(f"Error converting parsing run {run.run_id}: {e}", exc_info=True)
            continue
    
    # Сериализуем DTO с использованием alias для camelCase
    response_data = {
        "runs": [r.model_dump(by_alias=True, mode="json") for r in run_dtos],
        "total": total,
        "limit": limit,
        "offset": offset
    }
    return JSONResponse(content=response_data)


# CRITICAL: More specific routes must be defined BEFORE less specific ones
# /runs/{run_id}/logs must come BEFORE /runs/{run_id}
# TEST: Try with different path pattern to avoid potential conflicts
@router.get("/runs/{run_id}/logs", name="get_parsing_logs")
async def get_parsing_logs_endpoint(
    run_id: str,
    db = Depends(get_db)
):
    """Get parsing logs for a specific run ID."""
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"[LOGS ENDPOINT] get_parsing_logs_endpoint called with run_id={run_id}")
    
    # Get parsing run to check if it exists
    # Если run не найден, возвращаем пустой объект вместо 404
    # Это нормальная ситуация, если run еще не создан или логи еще не сохранены
    run = await get_parsing_run.execute(db=db, run_id=run_id)
    if not run:
        # Возвращаем пустой объект, а не 404 - это нормальная ситуация
        return {"run_id": run_id, "parsing_logs": {}}
    
    # Extract parsing_logs from process_log
    process_log = getattr(run, 'process_log', None)
    if process_log and isinstance(process_log, dict):
        parsing_logs = process_log.get("parsing_logs", {})
        return {"run_id": run_id, "parsing_logs": parsing_logs}
    else:
        return {"run_id": run_id, "parsing_logs": {}}


@router.put("/runs/{run_id}/logs")
async def update_parsing_logs_endpoint(
    run_id: str,
    request_data: Dict[str, Any] = Body(default={}),
    db = Depends(get_db)
):
    """Update parsing logs for a specific run ID (incremental updates during parsing)."""
    import logging
    import json
    from fastapi import HTTPException
    from sqlalchemy import text
    
    logger = logging.getLogger(__name__)
    
    # Get parsing run to check if it exists
    run = await get_parsing_run.execute(db=db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Parsing run not found")
    
    # Get parsing_logs from request
    if isinstance(request_data, dict):
        parsing_logs = request_data.get("parsing_logs", {})
    else:
        parsing_logs = {}
    
    if not parsing_logs:
        return {"status": "no_logs_provided"}
    
    # Детальное логирование размера логов перед обновлением
    logs_json = json.dumps(parsing_logs, ensure_ascii=False)
    logs_size = len(logs_json)
    engines = list(parsing_logs.keys())
    logger.info(f"Updating parsing logs for run_id: {run_id}, size: {logs_size} bytes, engines: {engines}")
    
    # Детальное логирование для каждого движка
    for engine_name, engine_logs in parsing_logs.items():
        total_links = engine_logs.get("total_links", 0)
        pages_processed = engine_logs.get("pages_processed", 0)
        last_links_count = len(engine_logs.get("last_links", []))
        links_by_page_count = len(engine_logs.get("links_by_page", {}))
        logger.info(f"  {engine_name}: total_links={total_links}, pages_processed={pages_processed}, last_links_count={last_links_count}, pages_with_links={links_by_page_count}")
    
    # Update process_log with parsing_logs
    # Get existing process_log or create new one
    process_log = getattr(run, 'process_log', None)
    existing_process_log = process_log if process_log and isinstance(process_log, dict) else {}
    
    # Update only parsing_logs in process_log, keep other fields
    existing_process_log["parsing_logs"] = parsing_logs
    
    # Update in database
    try:
        process_log_json = json.dumps(existing_process_log, ensure_ascii=False)
        final_size = len(process_log_json)
        await db.execute(
            text("""
                UPDATE parsing_runs 
                SET process_log = CAST(:process_log AS jsonb)
                WHERE run_id = :run_id
            """),
            {
                "process_log": process_log_json,
                "run_id": run_id
            }
        )
        await db.commit()
        logger.info(f"Successfully updated parsing logs for run_id: {run_id}, final process_log size: {final_size} bytes")
        return {"status": "updated", "run_id": run_id}
    except Exception as e:
        logger.error(f"Error updating parsing logs for run_id {run_id}: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating parsing logs: {str(e)}")


@router.get("/runs/{run_id}", response_model=ParsingRunDTO)
async def get_parsing_run_endpoint(
    run_id: str,
    db = Depends(get_db)
):
    """Get parsing run by ID."""
    import logging
    logger = logging.getLogger(__name__)
    from datetime import datetime
    _agent_debug_log({
        "location": "parsing_runs.py:127",
        "message": "get_parsing_run_endpoint called",
        "data": {"run_id": run_id},
        "timestamp": int(datetime.utcnow().timestamp() * 1000),
        "sessionId": "debug-session",
        "runId": run_id,
        "hypothesisId": "D",
    })
    # CRITICAL FIX: Wrap get_parsing_run in try-except to catch AttributeError
    # SQLAlchemy might try to load results_count even if we don't access it
    try:
        run = await get_parsing_run.execute(db=db, run_id=run_id)
        run_status = getattr(run, 'status', None) if run else None
        _agent_debug_log({
            "location": "parsing_runs.py:128",
            "message": "get_parsing_run.execute returned",
            "data": {"run_id": run_id, "status": run_status, "has_run": run is not None},
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "sessionId": "debug-session",
            "runId": run_id,
            "hypothesisId": "D",
        })
    except AttributeError as e:
        if "results_count" in str(e):
            # SQLAlchemy tried to load results_count but model doesn't have it
            # Return error with instructions
            logger.error(f"AttributeError loading parsing run {run_id}: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Model version mismatch. Please restart Backend to load updated model."
            )
        else:
            raise
    
    if not run:
        raise HTTPException(status_code=404, detail="Parsing run not found")
    
    try:
        # Extract keyword from request.title or raw_keys_json
        # Wrap in try-except to catch any AttributeError from accessing run attributes
        keyword = "Unknown"
        try:
            pl = getattr(run, 'process_log', None)
            if isinstance(pl, dict):
                k0 = pl.get('keyword')
                if isinstance(k0, str) and k0.strip():
                    keyword = k0.strip()

            if run.request:
                if keyword == "Unknown" and getattr(run.request, 'title', None):
                    if run.request.title:
                        keyword = run.request.title

                if keyword == "Unknown" and getattr(run.request, 'raw_keys_json', None):
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
        except (AttributeError, KeyError) as e:
            # If accessing run.request or other attributes fails, just use default
            logger.warning(f"Error accessing run attributes: {e}")
            keyword = "Unknown"
        
        # CRITICAL FIX: Always calculate results_count from domains_queue
        # This completely avoids AttributeError by never accessing the model attribute
        from app.adapters.db.repositories import DomainQueueRepository
        domain_queue_repo = DomainQueueRepository(db)
        _, count = await domain_queue_repo.list(
            limit=1,
            offset=0,
            parsing_run_id=run_id
        )
        results_count = count if count > 0 else None
        queue_stats = {
            "total_domains": 0,
            "ahead_domains": 0,
            "ahead_runs": 0,
            "run_domains": 0,
            "active_run_id": None,
            "ahead_list": [],
        }
        try:
            qres = await db.execute(
                text(
                    """
                    WITH auto_runs AS (
                      SELECT
                        pr.run_id,
                        pr.created_at,
                        COALESCE(pr.process_log->'domain_parser_auto'->>'status','') AS auto_status,
                        GREATEST(
                          0,
                          (SELECT COUNT(DISTINCT dq.domain)::int FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id)
                          - COALESCE(NULLIF(pr.process_log->'domain_parser_auto'->>'processed','')::int, 0)
                          - COALESCE(NULLIF(pr.process_log->'domain_parser_auto'->>'skippedExisting','')::int, 0)
                        ) AS remaining
                      FROM parsing_runs pr
                    ),
                    current_run AS (
                      SELECT created_at, auto_status, remaining
                      FROM auto_runs
                      WHERE run_id = :run_id
                    ),
                    active AS (
                      SELECT run_id, created_at, auto_status, remaining
                      FROM auto_runs
                      WHERE auto_status IN ('queued', 'running')
                    )
                    SELECT
                      COALESCE((SELECT SUM(remaining) FROM active), 0) AS total_domains,
                      COALESCE((SELECT remaining FROM current_run), 0) AS run_domains,
                      COALESCE(
                        (
                          SELECT SUM(a.remaining)
                          FROM active a, current_run c
                          WHERE c.auto_status = 'queued'
                            AND a.auto_status = 'queued'
                            AND a.created_at < c.created_at
                        ),
                        0
                      ) AS ahead_domains,
                      COALESCE(
                        (
                          SELECT COUNT(*)
                          FROM active a, current_run c
                          WHERE c.auto_status = 'queued'
                            AND a.auto_status = 'queued'
                            AND a.created_at < c.created_at
                        ),
                        0
                      ) AS ahead_runs,
                      COALESCE(
                        (
                          SELECT run_id
                          FROM active
                          WHERE auto_status = 'running'
                          ORDER BY created_at ASC
                          LIMIT 1
                        ),
                        (
                          SELECT run_id
                          FROM active
                          WHERE auto_status = 'queued'
                          ORDER BY created_at ASC
                          LIMIT 1
                        )
                      ) AS active_run_id
                    """
                ),
                {"run_id": run_id},
            )
            qrow = qres.fetchone()
            if qrow:
                queue_stats = {
                    "total_domains": int(qrow[0] or 0),
                    "run_domains": int(qrow[1] or 0),
                    "ahead_domains": int(qrow[2] or 0),
                    "ahead_runs": int(qrow[3] or 0),
                    "active_run_id": str(qrow[4]) if qrow[4] else None,
                    "ahead_list": [],
                }
            ahead_res = await db.execute(
                text(
                    """
                    WITH auto_runs AS (
                      SELECT
                        pr.run_id,
                        pr.created_at,
                        COALESCE(pr.process_log->'domain_parser_auto'->>'status','') AS auto_status,
                        GREATEST(
                          0,
                          (SELECT COUNT(DISTINCT dq.domain)::int FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id)
                          - COALESCE(NULLIF(pr.process_log->'domain_parser_auto'->>'processed','')::int, 0)
                          - COALESCE(NULLIF(pr.process_log->'domain_parser_auto'->>'skippedExisting','')::int, 0)
                        ) AS remaining
                      FROM parsing_runs pr
                    ),
                    current_run AS (
                      SELECT created_at, auto_status
                      FROM auto_runs
                      WHERE run_id = :run_id
                    )
                    SELECT a.run_id, a.remaining
                    FROM auto_runs a, current_run c
                    WHERE c.auto_status = 'queued'
                      AND a.auto_status = 'queued'
                      AND a.created_at < c.created_at
                      AND a.remaining > 0
                    ORDER BY a.created_at ASC
                    LIMIT 20
                    """
                ),
                {"run_id": run_id},
            )
            queue_stats["ahead_list"] = [
                {"runId": str(r[0]), "remainingDomains": int(r[1] or 0)}
                for r in (ahead_res.fetchall() or [])
                if r and r[0]
            ]
        except Exception:
            logger.warning("Failed to calculate domain parser queue stats for run_id=%s", run_id, exc_info=True)
        from datetime import datetime
        _agent_debug_log({
            "location": "parsing_runs.py:176",
            "message": "results_count calculated",
            "data": {"run_id": run_id, "count": count, "results_count": results_count},
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "sessionId": "debug-session",
            "runId": run_id,
            "hypothesisId": "F",
        })
        
        # Create DTO with extracted keyword
        # Use getattr for all attributes to avoid AttributeError
        started_at = getattr(run, 'started_at', None)
        finished_at = getattr(run, 'finished_at', None)
        created_at = getattr(run, 'created_at', None)
        process_log = getattr(run, 'process_log', None)
        
        run_dict = {
            "runId": getattr(run, 'run_id', None),
            "keyword": keyword,
            "status": getattr(run, 'status', None),
            "startedAt": started_at.isoformat() if started_at else None,
            "finishedAt": finished_at.isoformat() if finished_at else None,
            "error": getattr(run, 'error_message', None),
            "resultsCount": results_count,
            "createdAt": created_at.isoformat() if created_at else None,
            "depth": getattr(run, 'depth', None),
            "source": getattr(run, 'source', None),
            "processLog": process_log if isinstance(process_log, dict) else None,
            "domainParserQueueTotalDomains": queue_stats["total_domains"],
            "domainParserQueueAheadDomains": queue_stats["ahead_domains"],
            "domainParserQueueAheadRuns": queue_stats["ahead_runs"],
            "domainParserQueueRunDomains": queue_stats["run_domains"],
            "domainParserQueueActiveRunId": queue_stats["active_run_id"],
            "domainParserQueueAheadList": queue_stats["ahead_list"],
        }
        _agent_debug_log({
            "location": "parsing_runs.py:193",
            "message": "Returning run_dict",
            "data": {"run_id": run_id, "status": run_dict["status"], "resultsCount": run_dict["resultsCount"]},
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "sessionId": "debug-session",
            "runId": run_id,
            "hypothesisId": "D",
        })
        return ParsingRunDTO.model_validate(run_dict)
    except Exception as e:
        logger.error(f"Error converting parsing run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing parsing run: {str(e)}")


@router.delete("/runs/bulk")
async def bulk_delete_parsing_runs_endpoint(
    request: Request,
    db = Depends(get_db)
):
    """Bulk delete parsing runs."""
    import logging
    import json
    from app.adapters.db.session import AsyncSessionLocal
    
    logger = logging.getLogger(__name__)
    
    # Получаем run_ids из body
    try:
        body = await request.json()
        if isinstance(body, list):
            run_ids = body
        elif isinstance(body, dict) and "run_ids" in body:
            run_ids = body["run_ids"]
        else:
            raise HTTPException(status_code=400, detail="Invalid request body. Expected list of run_ids or {run_ids: [...]}")
        
        if not isinstance(run_ids, list) or len(run_ids) == 0:
            raise HTTPException(status_code=400, detail="run_ids must be a non-empty list")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    
    logger.info(f"Bulk deleting {len(run_ids)} parsing runs")
    
    deleted_count = 0
    errors = []
    
    # CRITICAL: Use separate session for each delete to avoid transaction conflicts
    # This ensures each delete is completely independent
    for run_id in run_ids:
        # Create a new session for this delete
        async with AsyncSessionLocal() as delete_session:
            try:
                # Use direct SQL DELETE in separate session
                # Check if run exists first
                check_result = await delete_session.execute(
                    text("SELECT COUNT(*) FROM parsing_runs WHERE run_id = :run_id"),
                    {"run_id": run_id}
                )
                count_before = check_result.scalar()
                
                if count_before == 0:
                    errors.append(f"Run {run_id} not found")
                    continue
                
                # Delete the run
                delete_result = await delete_session.execute(
                    text("DELETE FROM parsing_runs WHERE run_id = :run_id"),
                    {"run_id": run_id}
                )
                
                if delete_result.rowcount > 0:
                    deleted_count += 1
                    
                    # Commit this delete FIRST, before audit log
                    # This ensures the delete is committed even if audit log fails
                    await delete_session.flush()
                    await delete_session.commit()
                    logger.info(f"Committed deletion of run {run_id} (rowcount: {delete_result.rowcount})")
                    
                    # Log to audit_log AFTER commit (in a separate transaction)
                    # This way audit log errors won't affect the delete
                    try:
                        from app.adapters.audit import log_audit
                        async with AsyncSessionLocal() as audit_session:
                            await log_audit(
                                db=audit_session,
                                table_name="parsing_runs",
                                operation="DELETE",
                                record_id=run_id,
                                changed_by="system"
                            )
                            await audit_session.commit()
                    except Exception as audit_err:
                        logger.warning(f"Error logging audit for run {run_id}: {audit_err}")
                        # Don't fail the delete if audit logging fails
                    
                    # CRITICAL: Close the session to ensure commit is finalized
                    await delete_session.close()
                    
                    # Verify deletion using a NEW session to ensure we read from DB, not cache
                    async with AsyncSessionLocal() as verify_session:
                        verify_result = await verify_session.execute(
                            text("SELECT COUNT(*) FROM parsing_runs WHERE run_id = :run_id"),
                            {"run_id": run_id}
                        )
                        count_after = verify_result.scalar()
                        if count_after > 0:
                            logger.error(f"CRITICAL: Run {run_id} still exists after commit! Attempting direct delete again...")
                            # Try direct delete one more time in new session
                            direct_delete = await verify_session.execute(
                                text("DELETE FROM parsing_runs WHERE run_id = :run_id"),
                                {"run_id": run_id}
                            )
                            await verify_session.flush()
                            await verify_session.commit()
                            logger.info(f"Second delete attempt for {run_id} - rowcount: {direct_delete.rowcount}")
                        else:
                            logger.info(f"Verified: Run {run_id} deleted successfully")
                else:
                    errors.append(f"Run {run_id} not deleted (rowcount: 0)")
            except Exception as e:
                logger.error(f"Error deleting parsing run {run_id}: {e}", exc_info=True)
                errors.append(f"Error deleting {run_id}: {str(e)}")
                try:
                    await delete_session.rollback()
                except:
                    pass
    
    logger.info(f"Successfully deleted {deleted_count} parsing runs")
    
    # Return response
    if errors:
        return JSONResponse(
            status_code=207,
            content={
                "deleted": deleted_count,
                "errors": errors,
                "total": len(run_ids)
            }
        )
    return JSONResponse(
        status_code=200,
        content={
            "deleted": deleted_count,
            "total": len(run_ids)
        }
    )


@router.delete("/runs/{run_id}", status_code=204)
async def delete_parsing_run_endpoint(
    run_id: str,
    db = Depends(get_db)
):
    """Delete parsing run by ID."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Deleting parsing run: {run_id}")
    
    try:
        logger.info(f"Calling delete_parsing_run.execute for {run_id}")
        success = await delete_parsing_run.execute(db=db, run_id=run_id)
        logger.info(f"delete_parsing_run.execute returned: {success}")
        if not success:
            logger.warning(f"Parsing run not found: {run_id}")
            raise HTTPException(status_code=404, detail="Parsing run not found")
        
        # CRITICAL: Commit the transaction FIRST, before audit log
        # This ensures the delete is committed even if audit log fails
        logger.info(f"Committing transaction for run {run_id}...")
        await db.flush()
        await db.commit()
        logger.info(f"Transaction committed for run {run_id}")
        
        # Log to audit_log AFTER commit (in a separate transaction)
        # This way audit log errors won't affect the delete
        try:
            from app.adapters.audit import log_audit
            from app.adapters.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as audit_session:
                await log_audit(
                    db=audit_session,
                    table_name="parsing_runs",
                    operation="DELETE",
                    record_id=run_id,
                    changed_by="system"
                )
                await audit_session.commit()
        except Exception as audit_err:
            logger.warning(f"Error logging audit for run {run_id}: {audit_err}")
            # Don't fail the delete if audit logging fails
        
        # CRITICAL: Verify deletion using a NEW session to ensure we read from DB, not cache
        # This ensures we're reading from the database, not from session cache
        from app.adapters.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as verify_session:
            verify_result = await verify_session.execute(
                text("SELECT COUNT(*) FROM parsing_runs WHERE run_id = :run_id"),
                {"run_id": run_id}
            )
            count_after_commit = verify_result.scalar()
            logger.info(f"Verification after commit - runs with run_id {run_id}: {count_after_commit}")
            
            if count_after_commit > 0:
                logger.error(f"CRITICAL: Run {run_id} still exists after commit! Attempting direct delete again...")
                # Try to delete again directly in new session
                direct_delete = await verify_session.execute(
                    text("DELETE FROM parsing_runs WHERE run_id = :run_id"),
                    {"run_id": run_id}
                )
                await verify_session.flush()
                await verify_session.commit()
                logger.info(f"Second delete attempt for {run_id} - rowcount: {direct_delete.rowcount}")
            else:
                logger.info(f"SUCCESS: Run {run_id} was successfully deleted!")
    except Exception as e:
        logger.error(f"Error deleting parsing run {run_id}: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting parsing run: {str(e)}")
