"""Use case for starting parsing."""
import uuid
import json
import os
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import ParsingRequestRepository, ParsingRunRepository
from app.adapters.parser_client import ParserClient
from app.config import settings
from app.usecases import create_keyword


def _agent_debug_log(payload: dict) -> None:
    """Debug logging function for agent diagnostics."""
    if os.environ.get("AGENT_DEBUG_LOG", "0") != "1":
        return
    try:
        import httpx
        httpx.post(
            "http://127.0.0.1:8765/agent-debug-log",
            json=payload,
            timeout=1.0
        )
    except Exception:
        pass

# Track running parsing tasks to prevent duplicates
_running_parsing_tasks = set()


def _normalize_keyword(value: str) -> str:
    return "".join(str(value or "").lower().split())


def _extract_keyword_from_request(request) -> str:
    try:
        if request and getattr(request, "title", None):
            return str(request.title)
        if request and getattr(request, "raw_keys_json", None):
            try:
                keys_data = json.loads(request.raw_keys_json)
                if isinstance(keys_data, list) and keys_data:
                    return str(keys_data[0])
                if isinstance(keys_data, dict) and "keys" in keys_data and keys_data["keys"]:
                    return str(keys_data["keys"][0])
            except Exception:
                pass
    except Exception:
        pass
    return ""


def _auto_mode() -> str:
    val = getattr(settings, "DOMAIN_PARSER_AUTO_MODE", None)
    if val is None or str(val).strip() == "":
        val = os.getenv("DOMAIN_PARSER_AUTO_MODE", "complete")
    return str(val).strip().lower()


def _auto_enabled() -> bool:
    val = getattr(settings, "DOMAIN_PARSER_AUTO_ENABLED", None)
    if val is None or str(val).strip() == "":
        val = os.getenv("DOMAIN_PARSER_AUTO_ENABLED", "1")
    return str(val).strip() == "1"


def _auto_early() -> bool:
    val = getattr(settings, "DOMAIN_PARSER_AUTO_EARLY", None)
    if val is None or str(val).strip() == "":
        val = os.getenv("DOMAIN_PARSER_AUTO_EARLY", "1")
    return str(val).strip() == "1"


def _auto_limit() -> int:
    val = getattr(settings, "DOMAIN_PARSER_AUTO_LIMIT", None)
    if val is None or str(val).strip() == "":
        val = os.getenv("DOMAIN_PARSER_AUTO_LIMIT", "3")
    try:
        return max(int(str(val).strip()), 1)
    except Exception:
        return 3


def _get_auto_sem():
    import app.usecases.start_parsing as start_parsing_module
    if not hasattr(start_parsing_module, "_auto_domain_parser_sem"):
        try:
            limit_raw = getattr(settings, "DOMAIN_PARSER_AUTO_MAX_CONCURRENCY", None)
            if limit_raw is None or str(limit_raw).strip() == "":
                limit_raw = os.getenv("DOMAIN_PARSER_AUTO_MAX_CONCURRENCY", "2")
            limit_n = max(int(str(limit_raw).strip()), 1)
        except Exception:
            limit_n = 2
        start_parsing_module._auto_domain_parser_sem = asyncio.Semaphore(limit_n)
    return start_parsing_module._auto_domain_parser_sem


def _mark_domain_seen(run_id: str, domain: str) -> bool:
    key = str(run_id or "").strip()
    dom = str(domain or "").strip().lower()
    if not key or not dom:
        return False
    seen = _auto_domain_parser_seen.setdefault(key, set())
    if dom in seen:
        return False
    seen.add(dom)
    return True


async def _update_domain_parser_auto_log(
    *, db, run_id: str, parser_run_id: str | None = None, patch: dict | None = None
) -> None:
    from sqlalchemy import text
    import json
    try:
        res = await db.execute(
            text("SELECT process_log FROM parsing_runs WHERE run_id = :run_id"),
            {"run_id": run_id},
        )
        row = res.fetchone()
        pl = row[0] if row else None
        if isinstance(pl, str):
            try:
                pl = json.loads(pl)
            except Exception:
                pl = None
        if not isinstance(pl, dict):
            pl = {}
        dp = pl.get("domain_parser_auto")
        if not isinstance(dp, dict):
            dp = {}

        if parser_run_id:
            existing = dp.get("parserRunIds")
            if not isinstance(existing, list):
                existing = []
            if parser_run_id not in existing:
                existing.append(parser_run_id)
            dp["parserRunIds"] = existing
            dp["lastParserRunId"] = parser_run_id

        if patch:
            for k, v in patch.items():
                dp[k] = v

        pl["domain_parser_auto"] = dp
        await db.execute(
            text(
                "UPDATE parsing_runs "
                "SET process_log = CAST(:process_log AS jsonb) "
                "WHERE run_id = :run_id"
            ),
            {"process_log": json.dumps(pl, ensure_ascii=False), "run_id": run_id},
        )
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


def _get_parsing_sem():
    import app.usecases.start_parsing as start_parsing_module
    if not hasattr(start_parsing_module, "_parsing_sem"):
        try:
            limit_raw = getattr(settings, "PARSING_MAX_CONCURRENCY", None)
            if limit_raw is None or str(limit_raw).strip() == "":
                limit_raw = os.getenv("PARSING_MAX_CONCURRENCY", "1")
            limit_n = max(int(str(limit_raw).strip()), 1)
        except Exception:
            limit_n = 1
        start_parsing_module._parsing_sem = asyncio.Semaphore(limit_n)
    return start_parsing_module._parsing_sem


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
        # Only override depth/source from request when caller kept defaults.
        # This allows cabinet submit flow to force depth=30 even if request.depth=25.
        if (depth == 10 or depth is None) and getattr(request, "depth", None):
            depth = int(request.depth)
        if ((not source) or str(source).strip() == "google") and getattr(request, "source", None):
            source = str(request.source)
    else:
        # Create parsing request first
        request = await request_repo.create({
            "title": keyword,
            "raw_keys_json": json.dumps([keyword]),
            "source": source,
            "depth": depth,
        })

    # Cache: avoid re-parsing same keyword within 30 days (based on last successful run)
    try:
        from sqlalchemy import text

        norm = _normalize_keyword(keyword)
        if norm:
            cutoff = datetime.utcnow() - timedelta(days=30)
            res = await db.execute(
                text(
                    "SELECT pr.run_id, pr.status, pr.finished_at "
                    "FROM parsing_runs pr "
                    "LEFT JOIN parsing_requests req ON pr.request_id = req.id "
                    "WHERE pr.status = 'completed' AND pr.finished_at IS NOT NULL "
                    "AND ("
                    "regexp_replace(lower(COALESCE(pr.process_log->>'keyword','')), '\\s+', '', 'g') = :norm "
                    "OR regexp_replace(lower(COALESCE(req.title,'')), '\\s+', '', 'g') = :norm "
                    ") "
                    "AND pr.finished_at >= :cutoff "
                    "ORDER BY pr.finished_at DESC "
                    "LIMIT 1"
                ),
                {"norm": norm, "cutoff": cutoff},
            )
            row = res.fetchone()
            if row:
                cached_run_id = str(row[0])
                cached_status = str(row[1] or "completed")

                # If this is a cabinet request, we still need a run linked to the request.
                # Otherwise the request will show no results (no run_ids -> no domains -> no suppliers).
                if request is not None:
                    try:
                        from sqlalchemy import text

                        run_id = str(uuid.uuid4())
                        run_repo = ParsingRunRepository(db)
                        now = datetime.utcnow()

                        cached_count = 0
                        try:
                            cnt_res = await db.execute(
                                text("SELECT COUNT(*) FROM domains_queue WHERE parsing_run_id = :rid"),
                                {"rid": cached_run_id},
                            )
                            cached_count = int(cnt_res.scalar() or 0)
                        except Exception:
                            cached_count = 0

                        cached_parser_run_id = f"auto_parser_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
                        process_log_payload = {
                            "keyword": keyword,
                            "depth": depth,
                            "source": source,
                            "status": "completed",
                            "started_at": now.isoformat(),
                            "finished_at": now.isoformat(),
                            "cached": True,
                            "cached_from": cached_run_id,
                        }
                        if _auto_enabled():
                            process_log_payload["domain_parser_auto"] = {
                                "status": "queued",
                                "parserRunId": cached_parser_run_id,
                                "mode": "cached_copy",
                                "startedAt": now.isoformat(),
                            }

                        await run_repo.create({
                            "run_id": run_id,
                            "request_id": request.id,
                            "status": "completed",
                            "source": source,
                            "depth": depth,
                            "started_at": now,
                            "finished_at": now,
                            "results_count": cached_count,
                            "process_log": process_log_payload,
                        })

                        cached_domains: list[str] = []
                        if cached_count > 0:
                            await db.execute(
                                text(
                                    "INSERT INTO domains_queue (domain, keyword, url, parsing_run_id, source, status) "
                                    "SELECT domain, keyword, url, :new_run, source, status "
                                    "FROM domains_queue WHERE parsing_run_id = :cached_run "
                                    "ON CONFLICT DO NOTHING"
                                ),
                                {"new_run": run_id, "cached_run": cached_run_id},
                            )
                            try:
                                dres = await db.execute(
                                    text(
                                        "SELECT DISTINCT domain FROM domains_queue "
                                        "WHERE parsing_run_id = :new_run ORDER BY domain ASC"
                                    ),
                                    {"new_run": run_id},
                                )
                                cached_domains = [str(x[0]).strip() for x in (dres.fetchall() or []) if x and x[0]]
                            except Exception:
                                cached_domains = []

                        await db.commit()

                        # Even for cached runs, auto enrichment must process unresolved domains for this request.
                        try:
                            if _auto_enabled() and cached_domains:
                                from app.transport.routers import domain_parser as domain_parser_router

                                parser_run_id = cached_parser_run_id
                                domains_for_auto = list(cached_domains)
                                skipped_existing = 0
                                try:
                                    filtered: list[str] = []
                                    for d in domains_for_auto:
                                        try:
                                            exists = await domain_parser_router._domain_exists_in_suppliers(d)
                                        except Exception:
                                            exists = False
                                        if exists:
                                            skipped_existing += 1
                                        else:
                                            filtered.append(d)
                                    domains_for_auto = filtered
                                except Exception:
                                    # Best-effort filter only; fallback to original list.
                                    domains_for_auto = list(cached_domains)
                                    skipped_existing = 0

                                if not domains_for_auto:
                                    await _update_domain_parser_auto_log(
                                        db=db,
                                        run_id=run_id,
                                        parser_run_id=parser_run_id,
                                        patch={
                                            "status": "completed",
                                            "mode": "cached_copy",
                                            "processed": 0,
                                            "total": 0,
                                            "skippedExisting": int(skipped_existing),
                                            "finishedAt": datetime.utcnow().isoformat(),
                                        },
                                    )
                                    return {
                                        "runId": run_id,
                                        "keyword": keyword,
                                        "status": "completed",
                                    }

                                await _update_domain_parser_auto_log(
                                    db=db,
                                    run_id=run_id,
                                    parser_run_id=parser_run_id,
                                    patch={
                                        "status": "running",
                                        "mode": "cached_copy",
                                        "startedAt": datetime.utcnow().isoformat(),
                                        "domains": len(domains_for_auto),
                                        "total": len(domains_for_auto),
                                        "skippedExisting": int(skipped_existing),
                                    },
                                )
                                try:
                                    domain_parser_router._parser_runs[parser_run_id] = {
                                        "runId": run_id,
                                        "parserRunId": parser_run_id,
                                        "status": "running",
                                        "processed": 0,
                                        "total": len(domains_for_auto),
                                        "results": [],
                                        "startedAt": datetime.utcnow().isoformat(),
                                        "auto": True,
                                        "mode": "cached_copy",
                                    }
                                except Exception:
                                    pass

                                async def _auto_domain_parser_task_cached():
                                    from app.adapters.db.session import AsyncSessionLocal
                                    try:
                                        await domain_parser_router._process_domain_parser_batch(
                                            parser_run_id,
                                            run_id,
                                            domains_for_auto,
                                        )
                                        run_state = domain_parser_router._parser_runs.get(parser_run_id) or {}
                                        async with AsyncSessionLocal() as mark_db:
                                            await _update_domain_parser_auto_log(
                                                db=mark_db,
                                                run_id=run_id,
                                                parser_run_id=parser_run_id,
                                                patch={
                                                    "status": "completed",
                                                    "processed": int(run_state.get("processed") or len(domains_for_auto)),
                                                    "total": int(run_state.get("total") or len(domains_for_auto)),
                                                    "skippedExisting": int(skipped_existing),
                                                    "finishedAt": datetime.utcnow().isoformat(),
                                                },
                                            )
                                    except Exception:
                                        async with AsyncSessionLocal() as mark_db:
                                            await _update_domain_parser_auto_log(
                                                db=mark_db,
                                                run_id=run_id,
                                                parser_run_id=parser_run_id,
                                                patch={
                                                    "status": "failed",
                                                    "finishedAt": datetime.utcnow().isoformat(),
                                                },
                                            )

                                asyncio.create_task(_auto_domain_parser_task_cached())
                        except Exception:
                            pass

                        return {
                            "run_id": run_id,
                            "keyword": keyword,
                            "status": "completed",
                            "cached": True,
                            "cached_from": cached_run_id,
                            "results_count": cached_count,
                        }
                    except Exception:
                        try:
                            await db.rollback()
                        except Exception:
                            pass

                return {
                    "run_id": cached_run_id,
                    "keyword": keyword,
                    "status": cached_status,
                    "cached": True,
                }
    except Exception:
        pass
    
    # Create parsing run
    run_id = str(uuid.uuid4())
    run_repo = ParsingRunRepository(db)
    
    run_parser_run_id = f"auto_parser_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    process_log_payload = {
        "keyword": keyword,
        "depth": depth,
        "source": source,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
    }
    if _auto_enabled():
        process_log_payload["domain_parser_auto"] = {
            "status": "queued",
            "parserRunId": run_parser_run_id,
            "mode": _auto_mode(),
            "startedAt": datetime.utcnow().isoformat(),
        }

    run = await run_repo.create({
        "run_id": run_id,
        "request_id": request.id,
        "status": "running",
        "source": source,
        "depth": depth,
        "started_at": datetime.utcnow(),
        "process_log": process_log_payload,
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
                        sem = _get_parsing_sem()
                        async with sem:
                            logger.info(
                                f"[PARSING SEM] Acquired slot for run_id={run_id} (keyword={keyword})"
                            )
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
                        # Persist suppliers for Cabinet LK (request -> suppliers)
                        # This powers GET /cabinet/requests/{request_id}/suppliers.
                        try:
                            from sqlalchemy import text
                            await bg_db.execute(
                                text(
                                    "CREATE TABLE IF NOT EXISTS request_suppliers ("
                                    "id BIGSERIAL PRIMARY KEY, "
                                    "request_id BIGINT NOT NULL, "
                                    "keyword TEXT, "
                                    "domain TEXT, "
                                    "name TEXT, "
                                    "email TEXT, "
                                    "phone TEXT, "
                                    "source_url TEXT, "
                                    "created_at TIMESTAMP NOT NULL DEFAULT NOW()"
                                    ")"
                                )
                            )
                            await bg_db.execute(
                                text(
                                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_request_suppliers_request_domain "
                                    "ON request_suppliers (request_id, domain)"
                                )
                            )
                        except Exception as e:
                            logger.warning(f"Failed to ensure request_suppliers table: {e}")

                        try:
                            from urllib.parse import urlparse

                            # Best-effort upsert: last write wins for contacts.
                            for supplier in suppliers or []:
                                if not isinstance(supplier, dict):
                                    continue
                                source_url = str(supplier.get("source_url") or "").strip()
                                if not source_url:
                                    continue
                                domain = urlparse(source_url).netloc.replace("www.", "").strip()
                                if not domain:
                                    continue

                                name = str(supplier.get("name") or "").strip() or None
                                email = str(supplier.get("email") or "").strip() or None
                                phone = str(supplier.get("phone") or "").strip() or None

                                await bg_db.execute(
                                    text(
                                        "INSERT INTO request_suppliers (request_id, keyword, domain, name, email, phone, source_url) "
                                        "VALUES (:request_id, :keyword, :domain, :name, :email, :phone, :source_url) "
                                        "ON CONFLICT (request_id, domain) DO UPDATE SET "
                                        "keyword = EXCLUDED.keyword, "
                                        "name = COALESCE(EXCLUDED.name, request_suppliers.name), "
                                        "email = COALESCE(EXCLUDED.email, request_suppliers.email), "
                                        "phone = COALESCE(EXCLUDED.phone, request_suppliers.phone), "
                                        "source_url = COALESCE(EXCLUDED.source_url, request_suppliers.source_url)"
                                    ),
                                    {
                                        "request_id": int(request.id),
                                        "keyword": str(keyword),
                                        "domain": str(domain),
                                        "name": name,
                                        "email": email,
                                        "phone": phone,
                                        "source_url": source_url,
                                    },
                                )
                        except Exception as e:
                            logger.warning(f"Failed to upsert request_suppliers for run_id {run_id}: {e}")

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
                        auto_queued = False
                        
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

                                                # Progressive domain parser: enrich each domain as soon as it appears.
                                                try:
                                                    if _auto_enabled() and _auto_mode() == "progressive":
                                                        if _mark_domain_seen(run_id, domain):
                                                            logger.info(
                                                                f"[AUTO DOMAIN PARSER][progressive] queue domain={domain} run_id={run_id}"
                                                            )
                                                            from app.transport.routers import domain_parser as domain_parser_router

                                                            parser_run_id = f"auto_domain_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
                                                            try:
                                                                domain_parser_router._parser_runs[parser_run_id] = {
                                                                    "runId": run_id,
                                                                    "parserRunId": parser_run_id,
                                                                    "status": "running",
                                                                    "processed": 0,
                                                                    "total": 1,
                                                                    "results": [],
                                                                    "startedAt": datetime.utcnow().isoformat(),
                                                                    "auto": True,
                                                                    "mode": "progressive",
                                                                }
                                                            except Exception:
                                                                pass

                                                            try:
                                                                await _update_domain_parser_auto_log(
                                                                    db=bg_db,
                                                                    run_id=run_id,
                                                                    parser_run_id=parser_run_id,
                                                                    patch={
                                                                        "status": "running",
                                                                        "mode": "progressive",
                                                                        "startedAt": datetime.utcnow().isoformat(),
                                                                        "processed": int(
                                                                            (pl_val.get("domain_parser_auto", {}) or {}).get("processed") or 0
                                                                        ),
                                                                        "total": int(
                                                                            (pl_val.get("domain_parser_auto", {}) or {}).get("total") or 0
                                                                        )
                                                                        + 1,
                                                                    },
                                                                )
                                                            except Exception:
                                                                pass

                                                            async def _auto_domain_task():
                                                                sem = _get_auto_sem()
                                                                async with sem:
                                                                    await domain_parser_router._process_domain_parser_batch(
                                                                        parser_run_id,
                                                                        run_id,
                                                                        [domain],
                                                                    )
                                                                try:
                                                                    await _update_domain_parser_auto_log(
                                                                        db=bg_db,
                                                                        run_id=run_id,
                                                                        parser_run_id=parser_run_id,
                                                                        patch={
                                                                            "status": "running",
                                                                            "processed": int(
                                                                                (
                                                                                    (
                                                                                        (pl_val.get("domain_parser_auto", {}) or {}).get(
                                                                                            "processed"
                                                                                        )
                                                                                        or 0
                                                                                    )
                                                                                )
                                                                            )
                                                                            + 1,
                                                                            "lastFinishedAt": datetime.utcnow().isoformat(),
                                                                            "lastDomain": domain,
                                                                        },
                                                                    )
                                                                except Exception:
                                                                    pass

                                                            task = asyncio.create_task(_auto_domain_task())
                                                            import app.usecases.start_parsing as start_parsing_module
                                                            if not hasattr(start_parsing_module, "_auto_domain_parser_tasks"):
                                                                start_parsing_module._auto_domain_parser_tasks = set()
                                                            start_parsing_module._auto_domain_parser_tasks.add(task)
                                                            task.add_done_callback(lambda t: start_parsing_module._auto_domain_parser_tasks.discard(t))
                                                except Exception:
                                                    pass

                                                # Early auto-trigger Domain Parser as soon as first domains appear.
                                                try:
                                                    if not auto_queued and _auto_enabled():
                                                        if _auto_early():
                                                            from sqlalchemy import text
                                                            pl_res = await bg_db.execute(
                                                                text("SELECT process_log FROM parsing_runs WHERE run_id = :run_id"),
                                                                {"run_id": run_id},
                                                            )
                                                            pl_row = pl_res.fetchone()
                                                            pl_val = pl_row[0] if pl_row else None
                                                            if isinstance(pl_val, str):
                                                                try:
                                                                    pl_val = json.loads(pl_val)
                                                                except Exception:
                                                                    pl_val = None
                                                            if not isinstance(pl_val, dict):
                                                                pl_val = {}
                                                            already = pl_val.get("domain_parser_auto")
                                                            if not isinstance(already, dict) or str(already.get("status") or "").lower() not in {
                                                                "queued",
                                                                "running",
                                                                "completed",
                                                            }:
                                                                import uuid as _uuid

                                                                parser_run_id = f"auto_parser_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{_uuid.uuid4().hex[:8]}"
                                                                pl_val["domain_parser_auto"] = {
                                                                    "status": "queued",
                                                                    "parserRunId": parser_run_id,
                                                                    "domains": 0,
                                                                    "startedAt": datetime.utcnow().isoformat(),
                                                                    "early": True,
                                                                }
                                                                await bg_db.execute(
                                                                    text(
                                                                        "UPDATE parsing_runs "
                                                                        "SET process_log = CAST(:process_log AS jsonb) "
                                                                        "WHERE run_id = :run_id"
                                                                    ),
                                                                    {
                                                                        "process_log": json.dumps(pl_val, ensure_ascii=False),
                                                                        "run_id": run_id,
                                                                    },
                                                                )
                                                                await bg_db.commit()
                                                                auto_queued = True
                                                except Exception:
                                                    pass
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
                                existing_res = await bg_db.execute(
                                    text("SELECT process_log FROM parsing_runs WHERE run_id = :run_id"),
                                    {"run_id": run_id},
                                )
                                existing_row = existing_res.fetchone()
                                existing_log = existing_row[0] if existing_row else None
                                if isinstance(existing_log, str):
                                    try:
                                        existing_log = json_module.loads(existing_log)
                                    except Exception:
                                        existing_log = None
                                if not isinstance(existing_log, dict):
                                    existing_log = {}
                                merged_log = dict(existing_log)
                                merged_log.update(process_info)
                                process_log_json = json_module.dumps(merged_log, ensure_ascii=False)
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

                                    # Auto-trigger Domain Parser enrichment after parsing completion
                                    try:
                                        # Safety guard: domain parser is heavy (Playwright). Allow disabling/limiting via env.
                                        if not _auto_enabled():
                                            logger.info(f"[AUTO DOMAIN PARSER] Disabled by env for run_id={run_id}")
                                            return
                                        if _auto_mode() == "progressive":
                                            logger.info(
                                                f"[AUTO DOMAIN PARSER] progressive mode enabled for run_id={run_id}; "
                                                "completion fallback is allowed when no progressive marker exists"
                                            )

                                        # Idempotency: do not trigger twice
                                        pl_res = await bg_db.execute(
                                            text("SELECT process_log FROM parsing_runs WHERE run_id = :run_id"),
                                            {"run_id": run_id},
                                        )
                                        pl_row = pl_res.fetchone()
                                        process_log_val = pl_row[0] if pl_row else None
                                        if isinstance(process_log_val, str):
                                            try:
                                                process_log_val = json.loads(process_log_val)
                                            except Exception:
                                                process_log_val = None
                                        if not isinstance(process_log_val, dict):
                                            process_log_val = {}

                                        already = process_log_val.get("domain_parser_auto")
                                        if isinstance(already, dict) and str(already.get("status") or "").lower() in {
                                            "queued",
                                            "running",
                                            "completed",
                                        }:
                                            logger.info(f"[AUTO DOMAIN PARSER] Already triggered for run_id={run_id}, skipping")
                                        else:
                                            dq_res = await bg_db.execute(
                                                text(
                                                    "SELECT DISTINCT domain "
                                                    "FROM domains_queue "
                                                    "WHERE parsing_run_id = :run_id "
                                                    "ORDER BY domain ASC"
                                                ),
                                                {"run_id": run_id},
                                            )
                                            domains = [str(x[0]).strip() for x in (dq_res.fetchall() or []) if x and x[0]]
                                            # Limit domain parser batch size to avoid overloading the machine.
                                            limit_n = _auto_limit()
                                            if len(domains) > limit_n:
                                                domains = domains[:limit_n]
                                            if domains:
                                                import uuid

                                                parser_run_id = f"auto_parser_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
                                                process_log_val["domain_parser_auto"] = {
                                                    "status": "queued",
                                                    "parserRunId": parser_run_id,
                                                    "domains": len(domains),
                                                    "startedAt": datetime.utcnow().isoformat(),
                                                }
                                                await bg_db.execute(
                                                    text(
                                                        "UPDATE parsing_runs "
                                                        "SET process_log = CAST(:process_log AS jsonb) "
                                                        "WHERE run_id = :run_id"
                                                    ),
                                                    {
                                                        "process_log": json.dumps(process_log_val, ensure_ascii=False),
                                                        "run_id": run_id,
                                                    },
                                                )
                                                await bg_db.commit()

                                                from app.transport.routers import domain_parser as domain_parser_router

                                                # Register in-memory status for monitoring (best-effort)
                                                try:
                                                    domain_parser_router._parser_runs[parser_run_id] = {
                                                        "runId": run_id,
                                                        "parserRunId": parser_run_id,
                                                        "status": "running",
                                                        "processed": 0,
                                                        "total": len(domains),
                                                        "results": [],
                                                        "startedAt": datetime.utcnow().isoformat(),
                                                        "auto": True,
                                                    }
                                                except Exception:
                                                    pass

                                                async def _auto_domain_parser_task():
                                                    try:
                                                        await domain_parser_router._process_domain_parser_batch(
                                                            parser_run_id,
                                                            run_id,
                                                            domains,
                                                        )
                                                        try:
                                                            async with AsyncSessionLocal() as mark_db:
                                                                pl2_res = await mark_db.execute(
                                                                    text("SELECT process_log FROM parsing_runs WHERE run_id = :run_id"),
                                                                    {"run_id": run_id},
                                                                )
                                                                pl2_row = pl2_res.fetchone()
                                                                pl2 = pl2_row[0] if pl2_row else None
                                                                if isinstance(pl2, str):
                                                                    try:
                                                                        pl2 = json.loads(pl2)
                                                                    except Exception:
                                                                        pl2 = None
                                                                if not isinstance(pl2, dict):
                                                                    pl2 = {}
                                                                dp = pl2.get("domain_parser_auto")
                                                                if isinstance(dp, dict):
                                                                    dp["status"] = "completed"
                                                                    dp["finishedAt"] = datetime.utcnow().isoformat()
                                                                    pl2["domain_parser_auto"] = dp
                                                                    await mark_db.execute(
                                                                        text(
                                                                            "UPDATE parsing_runs "
                                                                            "SET process_log = CAST(:process_log AS jsonb) "
                                                                            "WHERE run_id = :run_id"
                                                                        ),
                                                                        {
                                                                            "process_log": json.dumps(pl2, ensure_ascii=False),
                                                                            "run_id": run_id,
                                                                        },
                                                                    )
                                                                    await mark_db.commit()
                                                        except Exception:
                                                            pass
                                                    except Exception as e:
                                                        logger.warning(f"[AUTO DOMAIN PARSER] Failed for run_id={run_id}: {e}", exc_info=True)
                                                        try:
                                                            async with AsyncSessionLocal() as mark_db:
                                                                pl2_res = await mark_db.execute(
                                                                    text("SELECT process_log FROM parsing_runs WHERE run_id = :run_id"),
                                                                    {"run_id": run_id},
                                                                )
                                                                pl2_row = pl2_res.fetchone()
                                                                pl2 = pl2_row[0] if pl2_row else None
                                                                if isinstance(pl2, str):
                                                                    try:
                                                                        pl2 = json.loads(pl2)
                                                                    except Exception:
                                                                        pl2 = None
                                                                if not isinstance(pl2, dict):
                                                                    pl2 = {}
                                                                dp = pl2.get("domain_parser_auto")
                                                                if isinstance(dp, dict):
                                                                    dp["status"] = "failed"
                                                                    dp["error"] = str(e)[:800]
                                                                    dp["finishedAt"] = datetime.utcnow().isoformat()
                                                                    pl2["domain_parser_auto"] = dp
                                                                    await mark_db.execute(
                                                                        text(
                                                                            "UPDATE parsing_runs "
                                                                            "SET process_log = CAST(:process_log AS jsonb) "
                                                                            "WHERE run_id = :run_id"
                                                                        ),
                                                                        {
                                                                            "process_log": json.dumps(pl2, ensure_ascii=False),
                                                                            "run_id": run_id,
                                                                        },
                                                                    )
                                                                    await mark_db.commit()
                                                        except Exception:
                                                            pass

                                                asyncio.create_task(_auto_domain_parser_task())
                                                logger.info(
                                                    f"[AUTO DOMAIN PARSER] Started auto batch parserRunId={parser_run_id} for run_id={run_id}, domains={len(domains)}"
                                                )
                                            else:
                                                logger.info(f"[AUTO DOMAIN PARSER] No domains to process for run_id={run_id}")
                                    except Exception as e:
                                        logger.warning(f"[AUTO DOMAIN PARSER] Error preparing auto trigger for run_id={run_id}: {e}", exc_info=True)
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
                        def _format_parser_error(e: Exception) -> str:
                            try:
                                import httpx
                                if isinstance(e, httpx.HTTPStatusError) and getattr(e, "response", None) is not None:
                                    resp = e.response
                                    snippet = ""
                                    try:
                                        data = resp.json()
                                        snippet = str(data.get("detail") or data.get("message") or data)[:800]
                                    except Exception:
                                        try:
                                            snippet = (resp.text or "")[:800]
                                        except Exception:
                                            snippet = ""
                                    return f"HTTP {resp.status_code} from parser_service: {snippet}".strip()
                            except Exception:
                                pass
                            return str(e)

                        try:
                            # Collect process information for failed parsing
                            process_info_failed = {
                                "total_domains": saved_count if 'saved_count' in locals() else 0,
                                "errors_count": errors_count if 'errors_count' in locals() else 0,
                                "keyword": keyword,
                                "depth": depth,
                                "source": source,
                                "finished_at": datetime.utcnow().isoformat(),
                                "error": _format_parser_error(parse_error)[:1000],
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
                            error_msg = _format_parser_error(parse_error)[:1000]  # Limit error message length
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


async def resume_failed_run(
    db: AsyncSession,
    run_id: str,
    background_tasks=None,
):
    """Resume failed parsing run from last processed page."""
    import logging
    logger = logging.getLogger(__name__)
    run_repo = ParsingRunRepository(db)
    request_repo = ParsingRequestRepository(db)

    run = await run_repo.get_by_id(run_id)
    if not run:
        return {"status": "skipped"}
    status_val = str(getattr(run, "status", "") or "")
    if status_val not in {"failed", "running"}:
        return {"status": "skipped"}

    process_log = getattr(run, "process_log", None)
    if isinstance(process_log, str):
        try:
            process_log = json.loads(process_log)
        except Exception:
            process_log = None
    if not isinstance(process_log, dict):
        process_log = {}

    request = await request_repo.get_by_id(int(run.request_id))
    keyword = str(process_log.get("keyword") or _extract_keyword_from_request(request) or "").strip()
    depth = int(getattr(run, "depth", None) or process_log.get("depth") or 10)
    source = str(getattr(run, "source", None) or process_log.get("source") or "google")

    resume_from: dict[str, int] = {}
    parsing_logs = process_log.get("parsing_logs") if isinstance(process_log.get("parsing_logs"), dict) else {}
    if isinstance(parsing_logs, dict):
        for engine, logs in parsing_logs.items():
            try:
                pages_done = int((logs or {}).get("pages_processed") or 0)
            except Exception:
                pages_done = 0
            if pages_done > 0 and pages_done < depth:
                resume_from[str(engine)] = pages_done + 1

    now = datetime.utcnow()
    process_log.update(
        {
            "status": "running",
            "resumed_at": now.isoformat(),
            "resume_from": resume_from,
        }
    )

    from sqlalchemy import text
    await db.execute(
        text(
            "UPDATE parsing_runs "
            "SET status = 'running', error_message = NULL, finished_at = NULL, started_at = :started_at, "
            "process_log = CAST(:process_log AS jsonb) "
            "WHERE run_id = :run_id"
        ),
        {"started_at": now, "process_log": json.dumps(process_log, ensure_ascii=False), "run_id": run_id},
    )
    await db.commit()

    async def run_parsing_resume():
        logger.info(f"[RESUME] Starting resume for run_id: {run_id}, resume_from={resume_from}")
        parser_client = ParserClient(settings.parser_service_url)
        from app.adapters.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_db:
            try:
                sem = _get_parsing_sem()
                async with sem:
                    logger.info(
                        f"[PARSING SEM] Acquired slot for run_id={run_id} (resume)"
                    )
                    result = await parser_client.parse(
                        keyword=keyword,
                        depth=depth,
                        source=source,
                        run_id=run_id,
                        resume_from=resume_from if resume_from else None,
                    )
                parsing_logs_local = result.get("parsing_logs", {})
                from app.adapters.db.repositories import DomainQueueRepository
                domain_queue_repo = DomainQueueRepository(bg_db)

                suppliers = result.get("suppliers", [])
                saved_count = 0
                errors_count = 0
                for supplier in suppliers:
                    try:
                        source_url = supplier.get("source_url") if isinstance(supplier, dict) else None
                        if not source_url:
                            continue
                        from urllib.parse import urlparse
                        parsed_url = urlparse(source_url)
                        domain = parsed_url.netloc.replace("www.", "")
                        existing_entry = await domain_queue_repo.get_by_domain_keyword_run(
                            domain=domain,
                            keyword=keyword,
                            parsing_run_id=run_id
                        )
                        if not existing_entry:
                            url_source = supplier.get("source") if isinstance(supplier, dict) else None
                            if not url_source:
                                url_source = source
                            await domain_queue_repo.create({
                                "domain": domain,
                                "keyword": keyword,
                                "url": source_url,
                                "parsing_run_id": run_id,
                                "source": url_source,
                                "status": "pending"
                            })
                            saved_count += 1
                    except Exception:
                        errors_count += 1

                await bg_db.commit()

                process_info = {
                    "total_domains": saved_count,
                    "errors_count": errors_count,
                    "keyword": keyword,
                    "depth": depth,
                    "source": source,
                    "finished_at": datetime.utcnow().isoformat(),
                    "status": "completed",
                }
                if parsing_logs_local:
                    process_info["parsing_logs"] = parsing_logs_local

                existing_log = {}
                try:
                    pl_res = await bg_db.execute(
                        text("SELECT process_log FROM parsing_runs WHERE run_id = :run_id"),
                        {"run_id": run_id},
                    )
                    pl_row = pl_res.fetchone()
                    existing_log = pl_row[0] if pl_row else None
                    if isinstance(existing_log, str):
                        try:
                            existing_log = json.loads(existing_log)
                        except Exception:
                            existing_log = None
                    if not isinstance(existing_log, dict):
                        existing_log = {}
                except Exception:
                    existing_log = {}

                merged_log = dict(existing_log)
                merged_log.update(process_info)

                # Ensure auto enrichment marker survives resume completion.
                if _auto_enabled():
                    existing_auto = merged_log.get("domain_parser_auto")
                    if not isinstance(existing_auto, dict):
                        existing_auto = None
                    if not existing_auto:
                        parser_run_id = f"auto_parser_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
                        merged_log["domain_parser_auto"] = {
                            "status": "queued",
                            "parserRunId": parser_run_id,
                            "mode": _auto_mode(),
                            "startedAt": datetime.utcnow().isoformat(),
                        }

                await bg_db.execute(
                    text(
                        "UPDATE parsing_runs "
                        "SET status = :status, finished_at = :finished_at, process_log = CAST(:process_log AS jsonb) "
                        "WHERE run_id = :run_id"
                    ),
                    {
                        "status": "completed",
                        "finished_at": datetime.utcnow(),
                        "process_log": json.dumps(merged_log, ensure_ascii=False),
                        "run_id": run_id,
                    },
                )
                await bg_db.commit()
            except Exception as e:
                error_msg = str(e)[:1000]
                process_info_failed = {
                    "keyword": keyword,
                    "depth": depth,
                    "source": source,
                    "finished_at": datetime.utcnow().isoformat(),
                    "error": error_msg,
                    "status": "failed",
                    "resume_from": resume_from,
                }
                await bg_db.execute(
                    text(
                        "UPDATE parsing_runs "
                        "SET status = :status, error_message = :error_message, finished_at = :finished_at, process_log = CAST(:process_log AS jsonb) "
                        "WHERE run_id = :run_id"
                    ),
                    {
                        "status": "failed",
                        "error_message": error_msg,
                        "finished_at": datetime.utcnow(),
                        "process_log": json.dumps(process_info_failed, ensure_ascii=False),
                        "run_id": run_id,
                    },
                )
                await bg_db.commit()
            finally:
                await parser_client.close()

    if background_tasks is not None:
        background_tasks.add_task(run_parsing_resume)
    else:
        asyncio.create_task(run_parsing_resume())

    return {"status": "running", "run_id": run_id}
# Global in-memory guard for progressive domain parser auto-enrichment
_auto_domain_parser_seen: dict[str, set[str]] = {}
