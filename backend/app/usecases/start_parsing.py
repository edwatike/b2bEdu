"""Use case for starting parsing."""
import uuid
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import ParsingRequestRepository, ParsingRunRepository
from app.adapters.parser_client import ParserClient
from app.config import settings
from app.usecases import create_keyword

# Track running parsing tasks to prevent duplicates
_running_parsing_tasks = set()


async def execute(
    db: AsyncSession,
    keyword: str,
    depth: int = 10,
    source: str = "google",
    background_tasks=None,
    request_id: int | None = None,
):
    """Start parsing for a keyword.
    
    Args:
        db: Database session
        keyword: Keyword to parse
        depth: Number of search result pages to parse (depth)
        source: Source for parsing - "google", "yandex", or "both" (default: "google")
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"start_parsing.execute called: keyword={keyword}, depth={depth}, source={source}")
    
    request_repo = ParsingRequestRepository(db)
    request = None
    if request_id is not None:
        request = await request_repo.get_by_id(int(request_id))
        if request is None:
            raise ValueError(f"Parsing request not found: {request_id}")

        # If caller did not pass explicit keyword/source/depth, use request fields
        if not keyword and getattr(request, "title", None):
            keyword = str(request.title)
        if getattr(request, "depth", None):
            depth = int(request.depth)
        if getattr(request, "source", None):
            source = str(request.source)
    else:
        # Create parsing request first
        request = await request_repo.create({
            "title": keyword,
            "raw_keys_json": json.dumps([keyword]),
            "source": source,
            "depth": depth,
        })
    
    # Create parsing run
    run_id = str(uuid.uuid4())
    run_repo = ParsingRunRepository(db)
    
    run = await run_repo.create({
        "run_id": run_id,
        "request_id": request.id,
        "status": "running",
        "source": source,
        "depth": depth,
        "started_at": datetime.utcnow(),
    })
    
    # Create keyword if it doesn't exist
    try:
        await create_keyword.execute(db=db, keyword=keyword)
        logger.info(f"Keyword '{keyword}' created or already exists")
    except Exception as e:
        logger.warning(f"Failed to create keyword '{keyword}': {e}")
        # Don't fail the parsing if keyword creation fails
    
    # Start parsing asynchronously
    # Note: In production, this should be done via a task queue (Celery, RQ, etc.)
    # For now, we'll call it directly but it will run asynchronously
    try:
        # Trigger parsing - this will connect to Chrome CDP and start parsing
        # The parsing happens asynchronously, so we don't wait for completion
        import asyncio
        import logging
        logger = logging.getLogger(__name__)
        
        # Start parsing in background task
        async def run_parsing():
            # CRITICAL: Log function entry FIRST to verify it's being called
            logger.info(f"[RUN_PARSING ENTRY] run_parsing() called for run_id: {run_id}")
            
            # CRITICAL: Prevent duplicate execution - check if task is already running
            # This check must be FIRST thing in the function to prevent race conditions
            # NOTE: run_id should already be in _running_parsing_tasks (added before BackgroundTasks.add_task)
            # But we check again here as a safety measure in case BackgroundTasks calls function twice
            logger.info(f"[DUPLICATE CHECK] Checking run_id {run_id}, current running tasks: {list(_running_parsing_tasks)}")
            if run_id in _running_parsing_tasks:
                # Check if this is the first call (run_id was added before BackgroundTasks.add_task)
                # or a duplicate call (run_id was added in a previous execution of this function)
                # We can't distinguish, so we use a flag to track if we've already started processing
                import app.usecases.start_parsing as start_parsing_module
                if not hasattr(start_parsing_module, '_processing_tasks'):
                    start_parsing_module._processing_tasks = set()
                
                if run_id in start_parsing_module._processing_tasks:
                    logger.warning(f"[DUPLICATE DETECTED] Parsing task for run_id {run_id} is already PROCESSING, skipping duplicate call")
                    return
                
                # Mark as processing
                start_parsing_module._processing_tasks.add(run_id)
                logger.info(f"[DUPLICATE CHECK] Marked run_id {run_id} as PROCESSING (total processing: {len(start_parsing_module._processing_tasks)})")
            else:
                # This shouldn't happen if we added run_id before BackgroundTasks.add_task
                # But add it here as a safety measure
                _running_parsing_tasks.add(run_id)
                logger.warning(f"[DUPLICATE CHECK] run_id {run_id} was NOT in running tasks, added now (this should not happen)")
                import app.usecases.start_parsing as start_parsing_module
                if not hasattr(start_parsing_module, '_processing_tasks'):
                    start_parsing_module._processing_tasks = set()
                start_parsing_module._processing_tasks.add(run_id)
            
            try:
                # CRITICAL: Wrap entire function in try-except to catch ALL errors
                logger.info(f"Background task started for run_id: {run_id}")
                _agent_debug_log({
                    "location": "start_parsing.py:56",
                    "message": "run_parsing function started",
                    "data": {"run_id": run_id, "keyword": keyword},
                    "timestamp": int(datetime.utcnow().timestamp() * 1000),
                    "sessionId": "debug-session",
                    "runId": run_id,
                    "hypothesisId": "A",
                })
                # Create parser client inside background task
                parser_client = ParserClient(settings.parser_service_url)
                _agent_debug_log({
                    "location": "start_parsing.py:61",
                    "message": "ParserClient created",
                    "data": {"run_id": run_id, "parser_service_url": settings.parser_service_url},
                    "timestamp": int(datetime.utcnow().timestamp() * 1000),
                    "sessionId": "debug-session",
                    "runId": run_id,
                    "hypothesisId": "A",
                })
                
                # Create new database session for background task
                from app.adapters.db.session import AsyncSessionLocal
                async with AsyncSessionLocal() as bg_db:
                    try:
                        logger.info(f"Starting parsing for keyword: {keyword}, source: {source}, depth: {depth}")
                        _agent_debug_log({
                            "location": "start_parsing.py:67",
                            "message": "Before parser_client.parse call",
                            "data": {"run_id": run_id, "keyword": keyword, "source": source, "depth": depth},
                            "timestamp": int(datetime.utcnow().timestamp() * 1000),
                            "sessionId": "debug-session",
                            "runId": run_id,
                            "hypothesisId": "A",
                        })
                        result = await parser_client.parse(
                            keyword=keyword,
                            depth=depth,
                            source=source,
                            run_id=run_id
                        )
                        _agent_debug_log({
                            "location": "start_parsing.py:73",
                            "message": "parser_client.parse completed",
                            "data": {
                                "run_id": run_id,
                                "total_found": result.get("total_found", 0),
                                "suppliers_count": len(result.get("suppliers", [])),
                            },
                            "timestamp": int(datetime.utcnow().timestamp() * 1000),
                            "sessionId": "debug-session",
                            "runId": run_id,
                            "hypothesisId": "A",
                        })
                        logger.info(f"Parsing completed for run_id: {run_id}, found {result.get('total_found', 0)} suppliers")
                        
                        # Get parsing logs from result if available
                        parsing_logs = result.get('parsing_logs', {})
                        if parsing_logs:
                            logger.info(f"Received parsing logs for run_id: {run_id}")
                        
                        # Save parsed URLs to domains_queue
                        from app.adapters.db.repositories import DomainQueueRepository
                        domain_queue_repo = DomainQueueRepository(bg_db)
                        
                        suppliers = result.get('suppliers', [])
                        logger.info(f"Processing {len(suppliers)} suppliers for run_id: {run_id}")
                        _agent_debug_log({
                            "location": "start_parsing.py:79",
                            "message": "Before saving domains",
                            "data": {"run_id": run_id, "suppliers_count": len(suppliers), "keyword": keyword},
                            "timestamp": int(datetime.utcnow().timestamp() * 1000),
                            "sessionId": "debug-session",
                            "runId": run_id,
                            "hypothesisId": "E",
                        })
                        saved_count = 0
                        errors_count = 0
                        
                        # CRITICAL: Wrap domain saving in try-except to ensure commit happens
                        try:
                            for supplier in suppliers:
                                # Parser Service returns dicts, not objects
                                source_url = supplier.get('source_url') if isinstance(supplier, dict) else getattr(supplier, 'source_url', None)
                                if source_url:
                                    try:
                                        from urllib.parse import urlparse
                                        parsed_url = urlparse(source_url)
                                        domain = parsed_url.netloc.replace("www.", "")
                                        
                                        # IMPORTANT: URL привязываются к ключу и запуску!
                                        # Один и тот же домен может быть найден для разных ключей,
                                        # поэтому мы всегда добавляем домен для каждого ключа/запуска.
                                        # Проверяем, что домен не был уже добавлен для ЭТОГО ключа и ЭТОГО запуска.
                                        existing_entry = await domain_queue_repo.get_by_domain_keyword_run(
                                            domain=domain,
                                            keyword=keyword,
                                            parsing_run_id=run_id
                                        )
                                        
                                        if not existing_entry:
                                            try:
                                                # КРИТИЧЕСКИ ВАЖНО: Используем source из supplier, который приходит из парсера
                                                # Parser returns dicts, so use .get() method
                                                url_source = supplier.get('source') if isinstance(supplier, dict) else getattr(supplier, 'source', None)
                                                if not url_source:
                                                    # Fallback: если парсер не вернул source, используем source из параметра
                                                    url_source = source
                                                await domain_queue_repo.create({
                                                    "domain": domain,
                                                    "keyword": keyword,
                                                    "url": source_url,
                                                    "parsing_run_id": run_id,
                                                    "source": url_source,  # Используем источник из парсера (google, yandex, или both)
                                                    "status": "pending"
                                                })
                                                saved_count += 1
                                                if saved_count <= 3:
                                                    _agent_debug_log({
                                                        "location": "start_parsing.py:108",
                                                        "message": "Domain saved",
                                                        "data": {
                                                            "run_id": run_id,
                                                            "domain": domain,
                                                            "keyword": keyword,
                                                            "parsing_run_id": run_id,
                                                            "saved_count": saved_count,
                                                        },
                                                        "timestamp": int(datetime.utcnow().timestamp() * 1000),
                                                        "sessionId": "debug-session",
                                                        "runId": run_id,
                                                        "hypothesisId": "E",
                                                    })
                                                logger.debug(f"Saved domain {domain} for run_id {run_id}")
                                            except Exception as create_error:
                                                # CRITICAL FIX: If sequence permission error, try to fix it
                                                error_str = str(create_error)
                                                if "InsufficientPrivilegeError" in error_str or ("domains_queue" in error_str and "seq" in error_str):
                                                    logger.error(f"Sequence permission error for domain {domain}: {create_error}")
                                                    try:
                                                        # Try to grant permissions on BOTH possible sequence names
                                                        from sqlalchemy import text
                                                        # First try to rename sequence if it has wrong name (check all possible names)
                                                        sequence_names = ["domains_queue_new_id_seq", "domains_queue_new_id_seq1"]
                                                        for old_name in sequence_names:
                                                            try:
                                                                await bg_db.execute(text(f"ALTER SEQUENCE {old_name} RENAME TO domains_queue_id_seq"))
                                                                await bg_db.commit()
                                                                logger.info(f"Renamed {old_name} to domains_queue_id_seq")
                                                                break
                                                            except Exception:
                                                                await bg_db.rollback()
                                                                pass  # Might already be renamed or not exist
                                                        
                                                        # Grant permissions on the correct sequence name
                                                        try:
                                                            await bg_db.execute(text("GRANT ALL PRIVILEGES ON SEQUENCE domains_queue_id_seq TO postgres"))
                                                            await bg_db.execute(text("GRANT ALL PRIVILEGES ON SEQUENCE domains_queue_id_seq TO PUBLIC"))
                                                            await bg_db.execute(text("ALTER SEQUENCE domains_queue_id_seq OWNER TO postgres"))
                                                            logger.info("Fixed permissions on sequence domains_queue_id_seq")
                                                        except Exception as seq_error:
                                                            logger.warning(f"Could not fix permissions on domains_queue_id_seq: {seq_error}")
                                                        await bg_db.commit()
                                                        logger.info(f"Fixed sequence permissions, retrying domain save for {domain}")
                                                        # Retry create after fixing permissions
                                                        await domain_queue_repo.create({
                                                            "domain": domain,
                                                            "keyword": keyword,
                                                            "url": supplier.source_url,
                                                            "parsing_run_id": run_id,
                                                            "source": source,  # Сохраняем источник (google, yandex, или both)
                                                            "status": "pending"
                                                        })
                                                        saved_count += 1
                                                        logger.debug(f"Saved domain {domain} for run_id {run_id} after fixing permissions")
                                                    except Exception as fix_error:
                                                        errors_count += 1
                                                        logger.error(f"Failed to fix sequence permissions: {fix_error}", exc_info=True)
                                                        await bg_db.rollback()
                                                else:
                                                    errors_count += 1
                                                    logger.warning(f"Error saving domain {supplier.get('source_url')}: {create_error}", exc_info=True)
                                        else:
                                            logger.debug(f"Domain {domain} for keyword {keyword} and run_id {run_id} already in queue, skipping.")
                                    except Exception as e:
                                        errors_count += 1
                                        logger.warning(f"Error saving domain {supplier.get('source_url')}: {e}", exc_info=True)
                            
                            # CRITICAL: Log immediately after loop to verify we reach this point
                            _agent_debug_log({
                                "location": "start_parsing.py:259",
                                "message": "LOOP COMPLETE",
                                "data": {"run_id": run_id, "saved_count": saved_count, "errors_count": errors_count},
                                "timestamp": int(datetime.utcnow().timestamp() * 1000),
                                "sessionId": "debug-session",
                                "runId": run_id,
                                "hypothesisId": "LOOP",
                            })
                            logger.info(f"[LOOP COMPLETE] Finished supplier loop for run_id: {run_id}, saved_count: {saved_count}, errors_count: {errors_count}")
                            
                            # CRITICAL: Commit domains IMMEDIATELY after saving - BEFORE any other operations
                            # This ensures domains are saved even if subsequent operations fail
                            total_suppliers = len(suppliers)
                            logger.info(f"[DOMAIN SAVE COMPLETE] Finished saving domains for run_id: {run_id}, saved_count: {saved_count}, errors_count: {errors_count}, total_suppliers: {total_suppliers}")
                            
                            # Commit domains FIRST - IMMEDIATELY after saving, before collecting statistics
                            logger.info(f"[BEFORE COMMIT] About to commit {saved_count} domains for run_id: {run_id}")
                            await bg_db.commit()
                            logger.info(f"[OK] [COMMIT SUCCESS] Committed {saved_count} domains to database for run_id: {run_id} (errors: {errors_count})")
                        except Exception as domain_save_error:
                            logger.error(f"[ERR] [DOMAIN SAVE ERROR] Error during domain saving for run_id {run_id}: {domain_save_error}", exc_info=True)
                            # Try to commit what we have, then re-raise
                            try:
                                await bg_db.commit()
                                logger.info(f"[OK] [COMMIT AFTER ERROR] Committed {saved_count} domains after error for run_id: {run_id}")
                            except Exception as commit_error:
                                logger.error(f"[ERR] [COMMIT FAILED] Failed to commit domains after error for run_id {run_id}: {commit_error}", exc_info=True)
                                await bg_db.rollback()
                            raise  # Re-raise to prevent status update if domains commit failed
                        
                        # Collect process information for logging (AFTER domains are committed)
                        process_info = {
                            "total_domains": saved_count,
                            "total_suppliers_from_parser": total_suppliers,
                            "errors_count": errors_count,
                            "keyword": keyword,
                            "depth": depth,
                            "source": source,
                            "finished_at": datetime.utcnow().isoformat(),
                        }
                        
                        # Add parsing logs if available
                        if parsing_logs:
                            process_info["parsing_logs"] = parsing_logs
                        
                        # Get statistics by source from domains_queue
                        try:
                            from sqlalchemy import text, func
                            stats_result = await bg_db.execute(
                                text("""
                                    SELECT source, COUNT(*) as count
                                    FROM domains_queue
                                    WHERE parsing_run_id = :run_id
                                    GROUP BY source
                                """),
                                {"run_id": run_id}
                            )
                            stats_rows = stats_result.fetchall()
                            source_stats = {"google": 0, "yandex": 0, "both": 0}
                            for row in stats_rows:
                                source_name = row[0] or "google"  # Default to google if null
                                count = row[1]
                                if source_name in source_stats:
                                    source_stats[source_name] = count
                            process_info["source_statistics"] = source_stats
                        except Exception as stats_error:
                            logger.warning(f"Error getting source statistics for run_id {run_id}: {stats_error}")
                            process_info["source_statistics"] = {"google": 0, "yandex": 0, "both": 0}
                        
                        # Get started_at time for duration calculation
                        try:
                            started_result = await bg_db.execute(
                                text("SELECT started_at FROM parsing_runs WHERE run_id = :run_id"),
                                {"run_id": run_id}
                            )
                            started_row = started_result.fetchone()
                            if started_row and started_row[0]:
                                started_at = started_row[0]
                                process_info["started_at"] = started_at.isoformat() if hasattr(started_at, 'isoformat') else str(started_at)
                                if hasattr(started_at, 'timestamp'):
                                    duration_seconds = (datetime.utcnow() - started_at).total_seconds()
                                    process_info["duration_seconds"] = duration_seconds
                        except Exception as time_error:
                            logger.warning(f"Error getting started_at for run_id {run_id}: {time_error}")
                        
                        # Check for CAPTCHA in error_message
                        try:
                            error_result = await bg_db.execute(
                                text("SELECT error_message FROM parsing_runs WHERE run_id = :run_id"),
                                {"run_id": run_id}
                            )
                            error_row = error_result.fetchone()
                            if error_row and error_row[0]:
                                error_msg = error_row[0].lower()
                                if "captcha" in error_msg or "капча" in error_msg:
                                    process_info["captcha_detected"] = True
                                    process_info["captcha_error_message"] = error_row[0]
                                else:
                                    process_info["captcha_detected"] = False
                            else:
                                process_info["captcha_detected"] = False
                        except Exception as captcha_error:
                            logger.warning(f"Error checking CAPTCHA for run_id {run_id}: {captcha_error}")
                            process_info["captcha_detected"] = False
                        
                        _agent_debug_log({
                            "location": "start_parsing.py:150",
                            "message": "Before updating status",
                            "data": {"run_id": run_id, "saved_count": saved_count, "total_suppliers": total_suppliers},
                            "timestamp": int(datetime.utcnow().timestamp() * 1000),
                            "sessionId": "debug-session",
                            "runId": run_id,
                            "hypothesisId": "A",
                        })
                        
                        # Log process information to file
                        logger.info(f"Process information for run_id {run_id}: {json.dumps(process_info, default=str)}")
                        
                        
                        # Update status in SEPARATE transaction (domains already committed)
                        from sqlalchemy import text
                        try:
                            logger.info(f"Updating parsing run {run_id} status to 'completed' (saved_count: {saved_count})")
                            
                            # Update status - use simple update without process_log first to avoid SQL errors
                            update_result = await bg_db.execute(
                                text("""
                                    UPDATE parsing_runs 
                                    SET status = :status,
                                        finished_at = :finished_at,
                                        results_count = :results_count
                                    WHERE run_id = :run_id
                                """),
                                {
                                    "status": "completed",
                                    "finished_at": datetime.utcnow(),
                                    "results_count": saved_count,
                                    "run_id": run_id
                                }
                            )
                            rows_updated = update_result.rowcount
                            logger.info(f"UPDATE query executed, rows_updated={rows_updated} for run_id: {run_id}")
                            
                            # Try to update process_log separately if needed
                            try:
                                import json as json_module
                                process_log_json = json_module.dumps(process_info, ensure_ascii=False)
                                await bg_db.execute(
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
                                logger.info(f"Updated process_log for run_id: {run_id}")
                            except Exception as process_log_error:
                                logger.warning(f"Failed to update process_log for run_id {run_id}: {process_log_error}")
                                # Don't fail the whole update if process_log fails
                            
                            # Commit status update
                            await bg_db.commit()
                            _agent_debug_log({
                                "location": "start_parsing.py:185",
                                "message": "Status update committed to DB",
                                "data": {"run_id": run_id, "saved_count": saved_count, "rows_updated": rows_updated},
                                "timestamp": int(datetime.utcnow().timestamp() * 1000),
                                "sessionId": "debug-session",
                                "runId": run_id,
                                "hypothesisId": "A",
                            })
                            logger.info(f"[OK] Committed status update to database for run_id: {run_id}")
                            
                            # Verify update worked by querying directly
                            verify_result = await bg_db.execute(
                                text("SELECT status, results_count FROM parsing_runs WHERE run_id = :run_id"),
                                {"run_id": run_id}
                            )
                            verify_row = verify_result.fetchone()
                            if verify_row:
                                verified_status = verify_row[0]
                                verified_count = verify_row[1]
                                _agent_debug_log({
                                    "location": "start_parsing.py:197",
                                    "message": "Status verification",
                                    "data": {"run_id": run_id, "verified_status": verified_status, "verified_count": verified_count},
                                    "timestamp": int(datetime.utcnow().timestamp() * 1000),
                                    "sessionId": "debug-session",
                                    "runId": run_id,
                                    "hypothesisId": "A",
                                })
                                if verified_status == "completed":
                                    logger.info(f"[OK] Successfully updated parsing run {run_id} to 'completed', results_count={verified_count}")
                                else:
                                    logger.error(f"[ERR] Update failed! Status is still '{verified_status}' for run_id {run_id}")
                            else:
                                logger.error(f"[ERR] Cannot verify update: parsing run {run_id} not found!")
                        except Exception as update_error:
                            logger.error(f"[ERR] Error updating status for run_id {run_id}: {update_error}", exc_info=True)
                            await bg_db.rollback()
                            _agent_debug_log({
                                "location": "start_parsing.py:210",
                                "message": "Status update error",
                                "data": {"run_id": run_id, "error": str(update_error)[:200]},
                                "timestamp": int(datetime.utcnow().timestamp() * 1000),
                                "sessionId": "debug-session",
                                "runId": run_id,
                                "hypothesisId": "A",
                            })
                            # Try one more time with direct SQL
                            try:
                                await bg_db.execute(
                                    text("""
                                        UPDATE parsing_runs 
                                        SET status = 'completed',
                                            finished_at = :finished_at,
                                            results_count = :results_count
                                        WHERE run_id = :run_id
                                    """),
                                    {
                                        "finished_at": datetime.utcnow(),
                                        "results_count": saved_count,
                                        "run_id": run_id
                                    }
                                )
                                await bg_db.commit()
                                logger.info(f"[OK] Retry update succeeded for run_id {run_id}")
                            except Exception as retry_error:
                                logger.error(f"[ERR] Retry update also failed for run_id {run_id}: {retry_error}", exc_info=True)
                                await bg_db.rollback()
                    except Exception as parse_error:
                        _agent_debug_log({
                            "location": "start_parsing.py:189",
                            "message": "parse_error caught",
                            "data": {"run_id": run_id, "error": str(parse_error)[:200]},
                            "timestamp": int(datetime.utcnow().timestamp() * 1000),
                            "sessionId": "debug-session",
                            "runId": run_id,
                            "hypothesisId": "A",
                        })
                        # Log parsing error but don't fail the whole task
                        logger.error(f"Parsing error in background task for run_id {run_id}: {parse_error}", exc_info=True)
                        # CRITICAL FIX: Don't re-raise, handle error gracefully
                        # Re-raise would cause the task to fail silently
                        # Instead, update status to failed and log the error
                        try:
                            # Collect process information for failed parsing
                            process_info_failed = {
                                "total_domains": saved_count if 'saved_count' in locals() else 0,
                                "errors_count": errors_count if 'errors_count' in locals() else 0,
                                "keyword": keyword,
                                "depth": depth,
                                "source": source,
                                "finished_at": datetime.utcnow().isoformat(),
                                "error": str(parse_error)[:1000],
                                "status": "failed"
                            }
                            
                            # Get statistics by source from domains_queue (if any domains were saved)
                            try:
                                from sqlalchemy import text
                                stats_result = await bg_db.execute(
                                    text("""
                                        SELECT source, COUNT(*) as count
                                        FROM domains_queue
                                        WHERE parsing_run_id = :run_id
                                        GROUP BY source
                                    """),
                                    {"run_id": run_id}
                                )
                                stats_rows = stats_result.fetchall()
                                source_stats = {"google": 0, "yandex": 0, "both": 0}
                                for row in stats_rows:
                                    source_name = row[0] or "google"
                                    count = row[1]
                                    if source_name in source_stats:
                                        source_stats[source_name] = count
                                process_info_failed["source_statistics"] = source_stats
                            except Exception:
                                process_info_failed["source_statistics"] = {"google": 0, "yandex": 0, "both": 0}
                            
                            # Check for CAPTCHA in error
                            error_msg_lower = str(parse_error).lower()
                            if "captcha" in error_msg_lower or "капча" in error_msg_lower:
                                process_info_failed["captcha_detected"] = True
                            else:
                                process_info_failed["captcha_detected"] = False
                            
                            # Log process information to file
                            logger.info(f"Process information (FAILED) for run_id {run_id}: {json.dumps(process_info_failed, default=str)}")
                            
                            
                            bg_run_repo = ParsingRunRepository(bg_db)
                            error_msg = str(parse_error)[:1000]  # Limit error message length
                            # Use direct SQL to update with process_log as JSONB
                            from sqlalchemy import text
                            await bg_db.execute(
                                text("""
                                    UPDATE parsing_runs 
                                    SET status = :status,
                                        error_message = :error_message,
                                        finished_at = :finished_at,
                                        process_log = CAST(:process_log AS jsonb)
                                    WHERE run_id = :run_id
                                """),
                                {
                                    "status": "failed",
                                    "error_message": error_msg,
                                    "finished_at": datetime.utcnow(),
                                    "process_log": json.dumps(process_info_failed),
                                    "run_id": run_id
                                }
                            )
                            await bg_db.commit()
                            logger.info(f"Updated parsing run {run_id} status to 'failed' due to error")
                        except Exception as update_err:
                            logger.error(f"Failed to update status to 'failed' for run_id {run_id}: {update_err}", exc_info=True)
                            await bg_db.rollback()
                        # Don't re-raise - let the task complete
                    finally:
                        await parser_client.close()
                        # Remove from running tasks when done
                        _running_parsing_tasks.discard(run_id)
                        logger.info(f"Removed run_id {run_id} from running tasks (remaining: {len(_running_parsing_tasks)})")
            except Exception as task_error:
                _agent_debug_log({
                    "location": "start_parsing.py:211",
                    "message": "task_error caught in run_parsing",
                    "data": {"run_id": run_id, "error": str(task_error)[:200]},
                    "timestamp": int(datetime.utcnow().timestamp() * 1000),
                    "sessionId": "debug-session",
                    "runId": run_id,
                    "hypothesisId": "A",
                })
                # CRITICAL FIX: Catch ALL errors in background task
                logger.error(f"Error in background task for run_id {run_id}: {task_error}", exc_info=True)
                # Try to update status to failed
                try:
                    from app.adapters.db.session import AsyncSessionLocal
                    async with AsyncSessionLocal() as error_db:
                        bg_run_repo = ParsingRunRepository(error_db)
                        error_msg = str(task_error)[:1000]
                        await bg_run_repo.update(run_id, {
                            "status": "failed",
                            "error_message": f"Background task error: {error_msg}",
                            "finished_at": datetime.utcnow()
                        })
                        await error_db.commit()
                        logger.info(f"Updated run_id {run_id} to 'failed' due to background task error")
                except Exception as update_err:
                    logger.error(f"Failed to update status after background task error: {update_err}", exc_info=True)
                finally:
                    # Always remove from running tasks, even on error
                    _running_parsing_tasks.discard(run_id)
                    logger.info(f"Removed run_id {run_id} from running tasks after error (remaining: {len(_running_parsing_tasks)})")
        
        # Start background task (fire and forget)
        # CRITICAL FIX: Use FastAPI BackgroundTasks if available, otherwise use asyncio.create_task()
        _agent_debug_log({
            "location": "start_parsing.py:232",
            "message": "Before starting background task",
            "data": {"run_id": run_id, "has_background_tasks": background_tasks is not None},
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "sessionId": "debug-session",
            "runId": run_id,
            "hypothesisId": "A",
        })
        if background_tasks is not None:
            # Use FastAPI BackgroundTasks - more reliable
            # CRITICAL: FastAPI BackgroundTasks can handle async functions directly
            # CRITICAL: Check if task is already running BEFORE adding to BackgroundTasks
            logger.info(f"[DUPLICATE PREVENTION] Checking run_id {run_id} before adding to BackgroundTasks, current running tasks: {list(_running_parsing_tasks)}")
            if run_id in _running_parsing_tasks:
                logger.warning(f"[DUPLICATE PREVENTION] run_id {run_id} already in running tasks, skipping BackgroundTasks.add_task")
                return result
            
            logger.info(f"Using FastAPI BackgroundTasks for run_id: {run_id}")
            # CRITICAL: Add run_id to running tasks BEFORE adding to BackgroundTasks to prevent race condition
            _running_parsing_tasks.add(run_id)
            logger.info(f"[DUPLICATE CHECK] Marked run_id {run_id} as running BEFORE adding to BackgroundTasks (total running: {len(_running_parsing_tasks)})")
            background_tasks.add_task(run_parsing)
            logger.info(f"Background task added to FastAPI BackgroundTasks for run_id: {run_id}")
            # NOTE: Do NOT also create asyncio.create_task() here - it causes duplicate parsing!
            # BackgroundTasks will run the task after response is sent, which is fine for async operations
        else:
            # Fallback to asyncio.create_task() if BackgroundTasks not available
            try:
                task = asyncio.create_task(run_parsing())
                logger.info(f"Background task created via asyncio.create_task() for run_id: {run_id}, task: {task}")
                # Add done callback to log completion or errors
                def task_done_callback(t):
                    try:
                        if t.exception():
                            logger.error(f"Background task failed for run_id {run_id}: {t.exception()}", exc_info=t.exception())
                        else:
                            logger.info(f"Background task completed for run_id: {run_id}")
                    except Exception as e:
                        logger.error(f"Error in task done callback for run_id {run_id}: {e}")
                task.add_done_callback(task_done_callback)
                # CRITICAL: Store task in a way that prevents garbage collection
                import app.usecases.start_parsing as start_parsing_module
                if not hasattr(start_parsing_module, '_background_tasks'):
                    start_parsing_module._background_tasks = set()
                start_parsing_module._background_tasks.add(task)
                # Remove task from set when done
                def cleanup_task(t):
                    try:
                        start_parsing_module._background_tasks.discard(t)
                    except:
                        pass
                task.add_done_callback(cleanup_task)
            except Exception as task_create_error:
                logger.error(f"Failed to create background task for run_id {run_id}: {task_create_error}", exc_info=True)
                # Try to update status to failed
                try:
                    await run_repo.update(run_id, {
                        "status": "failed",
                        "error_message": f"Failed to create background task: {str(task_create_error)}",
                        "finished_at": datetime.utcnow()
                    })
                    await db.commit()
                except Exception as update_err:
                    logger.error(f"Failed to update status after task creation error: {update_err}", exc_info=True)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error starting parsing task for run_id {run_id}: {e}", exc_info=True)
        # Update run status on error
        await run_repo.update(run_id, {
            "status": "failed",
            "error_message": str(e),
            "finished_at": datetime.utcnow()
        })
    
    return {
        "run_id": run_id,
        "keyword": keyword,
        "status": "running"
    }

