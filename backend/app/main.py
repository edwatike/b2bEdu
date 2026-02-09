"""FastAPI application entry point."""
import sys
import os
import asyncio
# Fix for MissingGreenlet issue on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
import json
import re
import uuid
from datetime import datetime

# CRITICAL: Ensure backend directory is in Python path for uvicorn reload mode
# When uvicorn runs with reload=True and import string, it spawns a new process
# that needs to have the correct Python path to import modules
# This is a safety measure in case PYTHONPATH is not set correctly
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_backend_dir, ".env"))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
import traceback
from sqlalchemy import text

from app.config import settings
from app.logging_config import setup_logging, log_service_event, get_logger
from app.adapters.db.session import AsyncSessionLocal
from app.usecases import start_parsing as start_parsing_usecase
from app.utils.rate_limit import limiter, PathRateLimitMiddleware
from app.transport.routers import (
    health,
    moderator_suppliers,
    moderator_users,
    keywords,
    blacklist,
    parsing,
    parsing_runs,
    domains_queue,
    attachments,
    checko,
    domain_parser,
    learning,
    domain_logs,
    auth,
    cabinet,
    mail,
    sync_workaround,
    current_task,
)

_DEBUG_MIDDLEWARE = (os.getenv("B2B_DEBUG_MIDDLEWARE", "0") or "").strip() == "1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Setup structured logging
    log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
    log_structured = getattr(settings, 'ENV', 'development') == 'production'
    log_file = getattr(settings, 'LOG_FILE', None)
    
    setup_logging(
        level=log_level,
        structured=log_structured,
        log_file=log_file
    )
    
    # Log startup event
    log_service_event(
        event_type="startup",
        service="backend",
        message="B2B Platform Backend starting up",
        port=8000,
        version="1.0.0"
    )

    # Security sanity checks (warnings only).
    try:
        from app.utils import auth as auth_utils

        if str(getattr(auth_utils, "SECRET_KEY", "")).startswith("your-super-secret"):
            get_logger("security").warning("JWT_SECRET/JWT_SECRET_KEY is not set; using insecure default.")
        if not str(getattr(settings, "USER_SECRETS_FERNET_KEY", "")).strip():
            get_logger("security").warning("USER_SECRETS_FERNET_KEY is empty; user secrets encryption is disabled.")
        if str(getattr(settings, "ENV", "")).lower() != "production":
            get_logger("security").warning("ENV is not 'production' (current=%s). Debug behavior may be enabled.", settings.ENV)
    except Exception:
        pass

    async def _startup_db_schema_checks() -> None:
        # Ensure DB schema is compatible with encrypted integration keys.
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS openai_api_key_encrypted TEXT"))
                await db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS groq_api_key_encrypted TEXT"))
                await db.commit()
        except Exception as e:
            logger = get_logger("db")
            logger.warning(f"DB schema check failed (openai_api_key_encrypted): {type(e).__name__}: {e}")

        # Ensure supplier data schema (domains/emails + INN uniqueness with exception).
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("ALTER TABLE moderator_suppliers ADD COLUMN IF NOT EXISTS allow_duplicate_inn BOOLEAN NOT NULL DEFAULT FALSE"))
                await db.execute(text("ALTER TABLE moderator_suppliers ADD COLUMN IF NOT EXISTS data_status VARCHAR(32) NOT NULL DEFAULT 'requires_moderation'"))

                # Enforce safer defaults at DB level (avoid supplier/complete without required contacts)
                try:
                    await db.execute(text("ALTER TABLE moderator_suppliers ALTER COLUMN type SET DEFAULT 'candidate'"))
                except Exception:
                    pass
                try:
                    await db.execute(text("ALTER TABLE moderator_suppliers ALTER COLUMN data_status SET DEFAULT 'requires_moderation'"))
                except Exception:
                    pass

                await db.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS supplier_domains ("
                        "id BIGSERIAL PRIMARY KEY, "
                        "supplier_id BIGINT NOT NULL REFERENCES moderator_suppliers(id) ON DELETE CASCADE, "
                        "domain VARCHAR(255) NOT NULL, "
                        "is_primary BOOLEAN NOT NULL DEFAULT FALSE, "
                        "created_at TIMESTAMP NOT NULL DEFAULT NOW(), "
                        "CONSTRAINT uq_supplier_domains_supplier_domain UNIQUE (supplier_id, domain)"
                        ")"
                    )
                )
                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_supplier_domains_domain ON supplier_domains (domain)"))
                await db.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS domain_moderation ("
                        "domain VARCHAR(255) PRIMARY KEY, "
                        "status VARCHAR(32) NOT NULL DEFAULT 'requires_moderation', "
                        "reason TEXT NULL, "
                        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                        ")"
                    )
                )
                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_domain_moderation_status ON domain_moderation (status)"))

                await db.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS supplier_emails ("
                        "id BIGSERIAL PRIMARY KEY, "
                        "supplier_id BIGINT NOT NULL REFERENCES moderator_suppliers(id) ON DELETE CASCADE, "
                        "email VARCHAR(320) NOT NULL, "
                        "is_primary BOOLEAN NOT NULL DEFAULT FALSE, "
                        "created_at TIMESTAMP NOT NULL DEFAULT NOW(), "
                        "CONSTRAINT uq_supplier_emails_supplier_email UNIQUE (supplier_id, email)"
                        ")"
                    )
                )
                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_supplier_emails_email ON supplier_emails (email)"))

                await db.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_suppliers_inn_unique "
                        "ON moderator_suppliers (inn) "
                        "WHERE inn IS NOT NULL AND allow_duplicate_inn = FALSE"
                    )
                )

                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_domains_queue_domain ON domains_queue (domain)"))
                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_domains_queue_parsing_run_id ON domains_queue (parsing_run_id)"))
                await db.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS moderator_tasks ("
                        "id BIGSERIAL PRIMARY KEY, "
                        "request_id BIGINT NOT NULL, "
                        "created_by BIGINT NOT NULL, "
                        "title TEXT, "
                        "status VARCHAR(32) NOT NULL DEFAULT 'new', "
                        "source VARCHAR(16) NOT NULL DEFAULT 'google', "
                        "depth INTEGER NOT NULL DEFAULT 30, "
                        "created_at TIMESTAMP NOT NULL DEFAULT NOW()"
                        ")"
                    )
                )
                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_moderator_tasks_status ON moderator_tasks (status)"))
                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_moderator_tasks_created_at ON moderator_tasks (created_at)"))

                await db.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS run_domains ("
                        "id BIGSERIAL PRIMARY KEY, "
                        "run_id VARCHAR(64) NOT NULL, "
                        "domain VARCHAR(255) NOT NULL, "
                        "status VARCHAR(32) NOT NULL DEFAULT 'pending', "
                        "reason TEXT, "
                        "attempted_urls JSONB DEFAULT '[]'::jsonb, "
                        "inn_source_url TEXT, "
                        "email_source_url TEXT, "
                        "supplier_id BIGINT REFERENCES moderator_suppliers(id) ON DELETE SET NULL, "
                        "checko_ok BOOLEAN NOT NULL DEFAULT FALSE, "
                        "global_requires_moderation BOOLEAN NOT NULL DEFAULT FALSE, "
                        "created_at TIMESTAMP NOT NULL DEFAULT NOW(), "
                        "updated_at TIMESTAMP NOT NULL DEFAULT NOW(), "
                        "CONSTRAINT uq_run_domains_run_domain UNIQUE (run_id, domain)"
                        ")"
                    )
                )
                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_run_domains_run_id ON run_domains (run_id)"))
                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_run_domains_status ON run_domains (status)"))
                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_run_domains_domain ON run_domains (domain)"))
                await db.execute(text("CREATE INDEX IF NOT EXISTS idx_run_domains_supplier_id ON run_domains (supplier_id)"))

                await db.execute(
                    text(
                        "INSERT INTO supplier_domains (supplier_id, domain, is_primary) "
                        "SELECT id, lower(domain), TRUE "
                        "FROM moderator_suppliers "
                        "WHERE domain IS NOT NULL AND trim(domain) <> '' "
                        "ON CONFLICT (supplier_id, domain) DO NOTHING"
                    )
                )
                await db.execute(
                    text(
                        "INSERT INTO supplier_emails (supplier_id, email, is_primary) "
                        "SELECT id, lower(email), TRUE "
                        "FROM moderator_suppliers "
                        "WHERE email IS NOT NULL AND trim(email) <> '' "
                        "ON CONFLICT (supplier_id, email) DO NOTHING"
                    )
                )

                await db.commit()
        except Exception as e:
            logger = get_logger("db")
            logger.warning(f"DB schema check failed (supplier domains/emails): {type(e).__name__}: {e}")

    asyncio.create_task(_startup_db_schema_checks())

    # -----------------------------------------------------------------------
    # STRICT FIFO domain parser queue worker  (v2 — resilient)
    # Finds runs with unprocessed domains, processes ONE run at a time.
    # Self-heals after restarts: resets stale 'running' → 'queued'.
    # -----------------------------------------------------------------------
    db_fail_streak = 0

    async def _domain_parser_queue_worker() -> None:
        w_logger = get_logger("domain_parser_worker")
        nonlocal db_fail_streak

        last_requeue_check_ts: float = 0.0

        # ── ONE-TIME startup recovery ──
        try:
            async with AsyncSessionLocal() as db:
                changed = False

                # (A) Reset stale 'running' → 'queued'
                stale_res = await db.execute(
                    text(
                        "SELECT run_id, process_log FROM parsing_runs "
                        "WHERE COALESCE(process_log->'domain_parser_auto'->>'status','') = 'running'"
                    )
                )
                for sr in (stale_res.fetchall() or []):
                    try:
                        rid = str(sr[0])
                        spl = sr[1]
                        if isinstance(spl, str):
                            try: spl = json.loads(spl)
                            except Exception: spl = {}
                        if not isinstance(spl, dict):
                            spl = {}
                        sdp = spl.get("domain_parser_auto")
                        if isinstance(sdp, dict):
                            sdp["status"] = "queued"
                            sdp["resetAt"] = datetime.utcnow().isoformat()
                            spl["domain_parser_auto"] = sdp
                            await db.execute(
                                text("UPDATE parsing_runs SET process_log = CAST(:pl AS jsonb) WHERE run_id = :rid"),
                                {"pl": json.dumps(spl, ensure_ascii=False), "rid": rid},
                            )
                            w_logger.info("Startup: reset 'running' → 'queued' for run %s", rid)
                            changed = True
                    except Exception:
                        w_logger.warning("Startup recovery failed for run %s", sr[0], exc_info=True)

                # (B) Re-queue 'completed'/'failed' runs that still have unprocessed domains
                requeue_res = await db.execute(
                    text(
                        "SELECT pr.run_id, pr.process_log "
                        "FROM parsing_runs pr "
                        "WHERE COALESCE(pr.process_log->'domain_parser_auto'->>'status','') IN ('completed','failed') "
                        "AND EXISTS ("
                        "SELECT 1 FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id "
                        "AND NOT EXISTS ("
                        "SELECT 1 FROM moderator_suppliers ms "
                        "LEFT JOIN supplier_domains sd ON sd.supplier_id = ms.id "
                        "WHERE replace(lower(COALESCE(sd.domain, ms.domain, '')), 'www.', '') = replace(lower(dq.domain), 'www.', '')"
                        ") "
                        "AND NOT EXISTS ("
                        "SELECT 1 FROM domain_moderation dm "
                        "WHERE replace(lower(dm.domain), 'www.', '') = replace(lower(dq.domain), 'www.', '') "
                        "AND COALESCE(dm.status, 'requires_moderation') = 'requires_moderation'"
                        ")"
                        ") "
                        "ORDER BY pr.created_at ASC LIMIT 10"
                    )
                )
                for rr in (requeue_res.fetchall() or []):
                    try:
                        rid = str(rr[0])
                        rpl = rr[1]
                        if isinstance(rpl, str):
                            try: rpl = json.loads(rpl)
                            except Exception: rpl = {}
                        if not isinstance(rpl, dict):
                            rpl = {}
                        rpl["domain_parser_auto"] = {
                            "status": "queued",
                            "parserRunId": f"auto_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
                            "mode": "recovery_startup",
                            "queuedAt": datetime.utcnow().isoformat(),
                        }
                        await db.execute(
                            text("UPDATE parsing_runs SET process_log = CAST(:pl AS jsonb) WHERE run_id = :rid"),
                            {"pl": json.dumps(rpl, ensure_ascii=False), "rid": rid},
                        )
                        w_logger.info("Startup: re-queued completed/failed run %s (has unprocessed domains)", rid)
                        changed = True
                    except Exception:
                        w_logger.warning("Startup re-queue failed for run %s", rr[0], exc_info=True)

                # (C) Populate run_domains for completed runs that don't have them yet,
                #     then re-queue runs that have pending run_domains
                try:
                    from app.transport.routers.current_task import _ensure_run_domains_populated
                    no_rd_res = await db.execute(
                        text(
                            "SELECT pr.run_id, pr.process_log "
                            "FROM parsing_runs pr "
                            "WHERE pr.status = 'completed' "
                            "AND EXISTS (SELECT 1 FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id) "
                            "AND NOT EXISTS (SELECT 1 FROM run_domains rd WHERE rd.run_id = pr.run_id) "
                            "ORDER BY pr.created_at DESC LIMIT 20"
                        )
                    )
                    for nrr in (no_rd_res.fetchall() or []):
                        try:
                            rid = str(nrr[0])
                            await _ensure_run_domains_populated(db, rid)
                            w_logger.info("Startup: populated run_domains for run %s", rid)
                        except Exception:
                            w_logger.warning("Startup: failed to populate run_domains for %s", nrr[0], exc_info=True)
                    await db.commit()

                    # Now re-queue runs with pending run_domains
                    pending_rd_res = await db.execute(
                        text(
                            "SELECT pr.run_id, pr.process_log "
                            "FROM parsing_runs pr "
                            "WHERE COALESCE(pr.process_log->'domain_parser_auto'->>'status','') IN ('completed','failed','') "
                            "AND EXISTS (SELECT 1 FROM run_domains rd WHERE rd.run_id = pr.run_id AND rd.status = 'pending') "
                            "ORDER BY pr.created_at ASC LIMIT 10"
                        )
                    )
                    for prr in (pending_rd_res.fetchall() or []):
                        try:
                            rid = str(prr[0])
                            rpl = prr[1]
                            if isinstance(rpl, str):
                                try: rpl = json.loads(rpl)
                                except Exception: rpl = {}
                            if not isinstance(rpl, dict):
                                rpl = {}
                            rpl["domain_parser_auto"] = {
                                "status": "queued",
                                "parserRunId": f"auto_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
                                "mode": "recovery_run_domains",
                                "queuedAt": datetime.utcnow().isoformat(),
                            }
                            await db.execute(
                                text("UPDATE parsing_runs SET process_log = CAST(:pl AS jsonb) WHERE run_id = :rid"),
                                {"pl": json.dumps(rpl, ensure_ascii=False), "rid": rid},
                            )
                            w_logger.info("Startup: re-queued run %s (has pending run_domains)", rid)
                            changed = True
                        except Exception:
                            w_logger.warning("Startup re-queue (run_domains) failed for %s", prr[0], exc_info=True)
                except Exception:
                    w_logger.warning("Startup recovery (C) failed", exc_info=True)

                if changed:
                    await db.commit()
        except Exception as e:
            w_logger.warning("Startup recovery failed: %s", e, exc_info=True)

        while True:
            try:
                # --- check enabled ---
                try:
                    from app.config import settings as _settings
                    auto_raw = getattr(_settings, "DOMAIN_PARSER_AUTO_ENABLED", None)
                except Exception:
                    auto_raw = None
                if auto_raw is None or str(auto_raw).strip() == "":
                    auto_raw = (os.getenv("DOMAIN_PARSER_AUTO_ENABLED", "1") or "1").strip()
                if str(auto_raw).strip() != "1":
                    await asyncio.sleep(10)
                    continue

                # --- check pause ---
                try:
                    if domain_parser._worker_paused:
                        await asyncio.sleep(3)
                        continue
                except Exception:
                    pass

                # --- periodic recovery B (re-queue completed/failed with unprocessed domains) ---
                try:
                    now_ts = time.time()
                except Exception:
                    now_ts = 0.0

                if now_ts and (now_ts - last_requeue_check_ts) >= 30:
                    last_requeue_check_ts = now_ts
                    try:
                        async with AsyncSessionLocal() as db:
                            requeue_res = await db.execute(
                                text(
                                    "SELECT pr.run_id, pr.process_log "
                                    "FROM parsing_runs pr "
                                    "WHERE COALESCE(pr.process_log->'domain_parser_auto'->>'status','') IN ('completed','failed') "
                                    "AND EXISTS (" 
                                    "SELECT 1 FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id "
                                    "AND NOT EXISTS (" 
                                    "SELECT 1 FROM moderator_suppliers ms "
                                    "LEFT JOIN supplier_domains sd ON sd.supplier_id = ms.id "
                                    "WHERE replace(lower(COALESCE(sd.domain, ms.domain, '')), 'www.', '') = replace(lower(dq.domain), 'www.', '')"
                                    ") "
                                    "AND NOT EXISTS (" 
                                    "SELECT 1 FROM domain_moderation dm "
                                    "WHERE replace(lower(dm.domain), 'www.', '') = replace(lower(dq.domain), 'www.', '') "
                                    "AND COALESCE(dm.status, 'requires_moderation') = 'requires_moderation'"
                                    ")"
                                    ") "
                                    "ORDER BY pr.created_at ASC LIMIT 10"
                                )
                            )
                            rows = requeue_res.fetchall() or []
                            changed = False
                            for rr in rows:
                                try:
                                    rid = str(rr[0])
                                    rpl = rr[1]
                                    if isinstance(rpl, str):
                                        try:
                                            rpl = json.loads(rpl)
                                        except Exception:
                                            rpl = {}
                                    if not isinstance(rpl, dict):
                                        rpl = {}

                                    rpl["domain_parser_auto"] = {
                                        "status": "queued",
                                        "parserRunId": f"auto_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
                                        "mode": "recovery_periodic",
                                        "queuedAt": datetime.utcnow().isoformat(),
                                    }
                                    await db.execute(
                                        text("UPDATE parsing_runs SET process_log = CAST(:pl AS jsonb) WHERE run_id = :rid"),
                                        {"pl": json.dumps(rpl, ensure_ascii=False), "rid": rid},
                                    )
                                    changed = True
                                except Exception:
                                    w_logger.warning("Periodic re-queue failed for run %s", rr[0], exc_info=True)

                            if changed:
                                await db.commit()
                    except Exception:
                        w_logger.warning("Periodic re-queue tick failed", exc_info=True)

                # ── Find work ──
                row = None
                try:
                    async with AsyncSessionLocal() as db:
                        # Recovery: mark runs WITHOUT domain_parser_auto marker as 'queued'
                        recover_res = await db.execute(
                            text(
                                "SELECT pr.run_id, pr.process_log "
                                "FROM parsing_runs pr "
                                "WHERE pr.status = 'completed' "
                                "AND COALESCE(pr.process_log->'domain_parser_auto'->>'status','') = '' "
                                "AND EXISTS (SELECT 1 FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id) "
                                "ORDER BY pr.created_at ASC LIMIT 20"
                            )
                        )
                        for rec in (recover_res.fetchall() or []):
                            try:
                                run_id = str(rec[0])
                                rpl = rec[1]
                                if isinstance(rpl, str):
                                    try: rpl = json.loads(rpl)
                                    except Exception: rpl = None
                                if not isinstance(rpl, dict):
                                    rpl = {}
                                rpl["domain_parser_auto"] = {
                                    "status": "queued",
                                    "parserRunId": f"auto_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
                                    "mode": "recovery",
                                    "queuedAt": datetime.utcnow().isoformat(),
                                }
                                await db.execute(
                                    text("UPDATE parsing_runs SET process_log = CAST(:pl AS jsonb) WHERE run_id = :rid"),
                                    {"pl": json.dumps(rpl, ensure_ascii=False), "rid": run_id},
                                )
                                w_logger.info("Recovery: queued unmarked run %s", run_id)
                            except Exception:
                                w_logger.warning("Recovery marker failed", exc_info=True)
                        await db.commit()

                        # Pick OLDEST run with status 'queued' (FIFO)
                        res = await db.execute(
                            text(
                                "SELECT pr.run_id, pr.process_log, "
                                "COALESCE(preq.title, preq.raw_keys_json, '') AS keyword "
                                "FROM parsing_runs pr "
                                "LEFT JOIN parsing_requests preq ON preq.id = pr.request_id "
                                "WHERE COALESCE(pr.process_log->'domain_parser_auto'->>'status','') = 'queued' "
                                "ORDER BY pr.created_at ASC LIMIT 1"
                            )
                        )
                        row = res.fetchone()
                    db_fail_streak = 0
                except Exception as e:
                    db_fail_streak += 1
                    backoff = min(60, 2 ** min(db_fail_streak, 5))
                    w_logger.warning("Worker DB error: %s (backoff %ss)", e, backoff, exc_info=True)
                    await asyncio.sleep(backoff)
                    continue

                if not row:
                    await asyncio.sleep(5)
                    continue

                # --- We have a run to process ---
                run_id = str(row[0])
                pl = row[1]
                keyword = str(row[2] or "") if len(row) > 2 else ""
                if isinstance(pl, str):
                    try: pl = json.loads(pl)
                    except Exception: pl = {}
                if not isinstance(pl, dict):
                    pl = {}
                dp = pl.get("domain_parser_auto")
                if not isinstance(dp, dict):
                    await asyncio.sleep(2)
                    continue
                parser_run_id = str(dp.get("parserRunId") or "").strip()
                if not parser_run_id:
                    await asyncio.sleep(2)
                    continue

                # Fetch ALL domains for this run
                try:
                    async with AsyncSessionLocal() as db:
                        dq_res = await db.execute(
                            text(
                                "SELECT DISTINCT domain FROM domains_queue "
                                "WHERE parsing_run_id = :run_id ORDER BY domain ASC"
                            ),
                            {"run_id": run_id},
                        )
                        all_domains = [str(x[0]).strip() for x in (dq_res.fetchall() or []) if x and x[0]]
                except Exception as e:
                    w_logger.warning("Failed to fetch domains for run %s: %s", run_id, e)
                    await asyncio.sleep(5)
                    continue

                total_all_domains = len(all_domains)

                # Eagerly populate run_domains so current-task block can see them
                try:
                    from app.transport.routers.current_task import _ensure_run_domains_populated
                    async with AsyncSessionLocal() as pop_db:
                        await _ensure_run_domains_populated(pop_db, run_id)
                except Exception:
                    w_logger.warning("Failed to pre-populate run_domains for %s", run_id, exc_info=True)

                # Use run_domains as source of truth: only process 'pending' domains
                try:
                    async with AsyncSessionLocal() as rd_db:
                        rd_res = await rd_db.execute(
                            text(
                                "SELECT domain FROM run_domains "
                                "WHERE run_id = :rid AND status = 'pending' "
                                "ORDER BY id ASC"
                            ),
                            {"rid": run_id},
                        )
                        domains = [str(r[0]) for r in (rd_res.fetchall() or []) if r and r[0]]
                except Exception:
                    # Fallback to old filter logic if run_domains query fails
                    try:
                        filtered = []
                        for d in all_domains:
                            try:
                                if await domain_parser._domain_exists_in_suppliers(d):
                                    continue
                                if await domain_parser._domain_requires_moderation(d):
                                    continue
                                filtered.append(d)
                            except Exception:
                                filtered.append(d)
                        domains = filtered
                    except Exception:
                        domains = list(all_domains)

                if not domains:
                    # All done — mark completed
                    try:
                        async with AsyncSessionLocal() as db:
                            dp["status"] = "completed"
                            dp["finishedAt"] = datetime.utcnow().isoformat()
                            dp["total"] = total_all_domains
                            dp["processed"] = total_all_domains
                            pl["domain_parser_auto"] = dp
                            await db.execute(
                                text("UPDATE parsing_runs SET process_log = CAST(:pl AS jsonb) WHERE run_id = :rid"),
                                {"pl": json.dumps(pl, ensure_ascii=False), "rid": run_id},
                            )
                            await db.commit()
                    except Exception:
                        pass
                    w_logger.info("FIFO: run %s — all domains processed, marked completed", run_id)
                    continue

                # Mark as running in DB
                try:
                    async with AsyncSessionLocal() as db:
                        dp["status"] = "running"
                        dp["pickedAt"] = datetime.utcnow().isoformat()
                        dp["domains"] = total_all_domains
                        dp["total"] = total_all_domains
                        pl["domain_parser_auto"] = dp
                        await db.execute(
                            text("UPDATE parsing_runs SET process_log = CAST(:pl AS jsonb) WHERE run_id = :rid"),
                            {"pl": json.dumps(pl, ensure_ascii=False), "rid": run_id},
                        )
                        await db.commit()
                except Exception:
                    pass

                # In-memory state for frontend
                try:
                    domain_parser._parser_runs[parser_run_id] = {
                        "runId": run_id, "parserRunId": parser_run_id,
                        "keyword": keyword, "status": "running",
                        "processed": int(dp.get("processed") or 0),
                        "total": total_all_domains,
                        "baseProcessed": int(dp.get("processed") or 0),
                        "overallTotal": total_all_domains,
                        "currentDomain": None, "currentSourceUrls": [],
                        "results": [], "startedAt": datetime.utcnow().isoformat(),
                        "auto": True,
                    }
                except Exception:
                    pass

                w_logger.info(
                    "FIFO: picked run_id=%s keyword='%s' parserRunId=%s domains=%d (of %d total)",
                    run_id, keyword, parser_run_id, len(domains), total_all_domains,
                )

                # Process ALL domains
                status_val = "completed"
                err_val = None
                try:
                    await domain_parser._process_domain_parser_batch(parser_run_id, run_id, domains)
                except Exception as e:
                    status_val = "failed"
                    err_val = str(e)[:800]
                    w_logger.error("Batch failed for run %s: %s", run_id, e, exc_info=True)

                # Mark final status in DB
                try:
                    run_state = domain_parser._parser_runs.get(parser_run_id) or {}
                    async with AsyncSessionLocal() as mark_db:
                        pl2_res = await mark_db.execute(
                            text("SELECT process_log FROM parsing_runs WHERE run_id = :rid"),
                            {"rid": run_id},
                        )
                        pl2_row = pl2_res.fetchone()
                        pl2 = pl2_row[0] if pl2_row else None
                        if isinstance(pl2, str):
                            try: pl2 = json.loads(pl2)
                            except Exception: pl2 = None
                        if not isinstance(pl2, dict):
                            pl2 = {}
                        dp2 = pl2.get("domain_parser_auto")
                        if isinstance(dp2, dict) and str(dp2.get("parserRunId") or "") == parser_run_id:
                            dp2["status"] = status_val
                            dp2["processed"] = int(run_state.get("processed") or dp2.get("processed") or 0)
                            dp2["total"] = int(run_state.get("total") or dp2.get("total") or len(domains))
                            if err_val:
                                dp2["error"] = err_val
                            if status_val in {"completed", "failed"}:
                                dp2["finishedAt"] = datetime.utcnow().isoformat()
                            pl2["domain_parser_auto"] = dp2
                            await mark_db.execute(
                                text("UPDATE parsing_runs SET process_log = CAST(:pl AS jsonb) WHERE run_id = :rid"),
                                {"pl": json.dumps(pl2, ensure_ascii=False), "rid": run_id},
                            )
                            await mark_db.commit()
                except Exception:
                    w_logger.warning("Failed to mark final status for run %s", run_id, exc_info=True)

                w_logger.info("FIFO: finished run_id=%s status=%s", run_id, status_val)

            except Exception as e:
                w_logger.warning("Domain parser worker tick failed: %s", str(e), exc_info=True)

            await asyncio.sleep(3)

    app.state._domain_parser_worker = asyncio.create_task(_domain_parser_queue_worker())

    async def _resume_failed_runs_worker() -> None:
        w_logger = get_logger("resume_failed_runs")
        await asyncio.sleep(5)
        try:
            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    text(
                        "SELECT run_id FROM parsing_runs "
                        "WHERE status IN ('failed','running') "
                        "ORDER BY finished_at DESC NULLS LAST, started_at DESC NULLS LAST "
                        "LIMIT 20"
                    )
                )
                rows = res.fetchall() or []
            run_ids = [str(r[0]) for r in rows if r and r[0]]
            import importlib
            start_parsing_module = importlib.import_module("app.usecases.start_parsing")
            for run_id in run_ids:
                try:
                    async with AsyncSessionLocal() as db:
                        await start_parsing_module.resume_failed_run(db=db, run_id=run_id, background_tasks=None)
                except Exception as e:
                    w_logger.warning("Failed to resume run_id=%s: %s", run_id, str(e), exc_info=True)
        except Exception as e:
            w_logger.warning("Resume failed runs worker error: %s", str(e), exc_info=True)

    app.state._resume_failed_runs_worker = asyncio.create_task(_resume_failed_runs_worker())
    
    yield

    try:
        task = getattr(app.state, "_domain_parser_worker", None)
        if task:
            task.cancel()
        resume_task = getattr(app.state, "_resume_failed_runs_worker", None)
        if resume_task:
            resume_task.cancel()
    except Exception:
        pass
    # Shutdown
    log_service_event(
        event_type="shutdown", 
        service="backend",
        message="B2B Platform Backend shutting down"
    )


app = FastAPI(
    title="B2B Platform API",
    version="1.0.0",
    description="API for B2B Platform - supplier moderation and parsing system",
    lifespan=lifespan,
)

# ── Rate Limiter ─────────────────────────────────────────────────────────
app.state.limiter = limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler as _rl_handler  # noqa: E402
app.add_exception_handler(RateLimitExceeded, _rl_handler)

# CRITICAL: Verify app is created correctly
logger = get_logger(__name__)
logger.info("FastAPI app instance created", extra={"app_id": id(app)})

# Log CORS configuration
logger.info("CORS configured", extra={
    "origins": settings.cors_origins_list,
    "app_id": id(app)
})

# Добавляем обработчик ошибок на уровне Starlette
from starlette.requests import Request as StarletteRequest

async def starlette_exception_handler(request: StarletteRequest, exc: Exception):
    """Starlette-level exception handler — unified format."""
    logger = get_logger(__name__)
    logger.error("Starlette exception", extra={
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "path": str(request.url.path) if hasattr(request, 'url') else None
    }, exc_info=True)
    
    error_detail = f"{type(exc).__name__}: {str(exc)}"
    if settings.ENV == "development":
        error_detail += f"\n{traceback.format_exc()}"
    
    response = JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": error_detail,
            "status": 500,
            "path": str(request.url.path) if hasattr(request, 'url') else "",
        }
    )
    
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

# Добавляем обработчик на уровне Starlette
app.add_exception_handler(Exception, starlette_exception_handler)


def _is_allowed_cors_origin(origin: str | None) -> bool:
    if not origin:
        return False
    if origin in settings.cors_origins_list:
        return True
    return bool(re.match(r"^https?://([a-z0-9-]+\.)*(ngrok-free\.app|ngrok\.io)$", origin))

# Temporarily disable all middleware to test MissingGreenlet issue
# CORS Middleware - должен быть первым
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.cors_origins_list,
#     allow_origin_regex=r"^https?://([a-z0-9-]+\.)*(ngrok-free\.app|ngrok\.io)$",
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
#     expose_headers=["*"],
# )

# Ngrok bypass middleware - добавляем заголовки для обхода ngrok warning
class NgrokBypassMiddleware(BaseHTTPMiddleware):
    """Middleware to bypass ngrok browser warning by adding required headers."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Добавляем заголовки для обхода ngrok warning ко всем ответам
        response.headers["ngrok-skip-browser-warning"] = "true"
        
        return response

# Temporarily disable all middleware to test MissingGreenlet issue
# app.add_middleware(NgrokBypassMiddleware)

# Middleware для обработки ошибок с CORS
from starlette.responses import Response
import json

class CORSExceptionMiddleware(BaseHTTPMiddleware):
    """Middleware для добавления CORS заголовков к ошибкам."""
    async def dispatch(self, request, call_next):
        import logging
        logger = logging.getLogger(__name__)
        
        # DEBUG: Log noisy diagnostics only when explicitly enabled
        if _DEBUG_MIDDLEWARE:
            if "/parsing/runs" in str(request.url.path) and "/logs" in str(request.url.path):
                logger.info(f"[DEBUG MIDDLEWARE] Request to: {request.method} {request.url.path}")
                logger.info(f"[DEBUG MIDDLEWARE] Request scope path: {request.scope.get('path', 'N/A')}")
                logger.info(f"[DEBUG MIDDLEWARE] Request scope method: {request.scope.get('method', 'N/A')}")
            
            # DEBUG: Log INN extraction requests
            if "/inn-extraction" in str(request.url.path):
                logger.info(f"[DEBUG MIDDLEWARE] INN extraction request: {request.method} {request.url.path}")
                logger.info(f"[DEBUG MIDDLEWARE] Available routes: {[r.path for r in app.routes if hasattr(r, 'path')][:10]}")
        
        try:
            response = await call_next(request)
            
            # DEBUG: Log response for /parsing/runs/*/logs
            if _DEBUG_MIDDLEWARE:
                if "/parsing/runs" in str(request.url.path) and "/logs" in str(request.url.path):
                    logger.info(f"[DEBUG MIDDLEWARE] Response status: {response.status_code}")
                    logger.info(f"[DEBUG MIDDLEWARE] Response headers: {dict(response.headers)}")
            
            # Убедимся, что CORS заголовки есть даже при ошибках
            origin = request.headers.get("origin")
            if _is_allowed_cors_origin(origin):
                if "Access-Control-Allow-Origin" not in response.headers:
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                    response.headers["Access-Control-Allow-Methods"] = "*"
                    response.headers["Access-Control-Allow-Headers"] = "*"
            return response
        except Exception as exc:
            import traceback
            # Безопасное логирование - оборачиваем в try-except
            try:
                logger.error(f"Exception in middleware: {type(exc).__name__}: {exc}", exc_info=True)
            except Exception:
                pass  # Если логирование не работает, просто пропускаем
            
            # Обработка исключений на уровне middleware
            
            error_detail = f"{type(exc).__name__}: {str(exc)}"
            if settings.ENV == "development":
                error_detail += f"\n{traceback.format_exc()}"
            
            response = JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "detail": error_detail,
                    "status": 500,
                    "path": str(request.url.path),
                }
            )
            
            origin = request.headers.get("origin")
            if _is_allowed_cors_origin(origin):
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "*"
                response.headers["Access-Control-Allow-Headers"] = "*"
            
            return response

# Temporarily disable all middleware to test MissingGreenlet issue
# app.add_middleware(CORSExceptionMiddleware)

# Ngrok warning bypass middleware
class NgrokWarningMiddleware(BaseHTTPMiddleware):
    """Middleware to bypass ngrok browser warning."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Check if this is an ngrok request
        if "ngrok" in request.headers.get("host", ""):
            # Add headers to bypass ngrok warning
            response.headers["ngrok-skip-browser-warning"] = "true"
        
        return response

# Temporarily disable all middleware to test MissingGreenlet issue
# app.add_middleware(NgrokWarningMiddleware)

# ── Path-based rate limiting for mail endpoints ──────────────────────────
# Temporarily disable all middleware to test MissingGreenlet issue
# app.add_middleware(
#     PathRateLimitMiddleware,
#     rules=[
#         ("/api/mail/", 10, 60),   # 10 req/min for all mail endpoints
#     ],
# )

# Global exception handler for debugging - ДОЛЖЕН быть ДО включения роутеров!
from fastapi.exceptions import HTTPException as FastAPIHTTPException

def _build_error_body(
    status_code: int,
    detail: str,
    path: str | None = None,
    error: str | None = None,
) -> dict:
    """Unified error response body used by ALL exception handlers."""
    from datetime import datetime, timezone

    return {
        "error": error or _status_to_error(status_code),
        "detail": detail,
        "status": status_code,
        "path": path or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _status_to_error(code: int) -> str:
    _MAP = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limit_exceeded",
        500: "internal_server_error",
        502: "bad_gateway",
        504: "gateway_timeout",
    }
    return _MAP.get(code, "error")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """422 Validation Error — unified format."""
    body = _build_error_body(
        status_code=422,
        detail=str(exc.errors()),
        path=str(request.url.path),
        error="validation_error",
    )
    response = JSONResponse(status_code=422, content=body)
    origin = request.headers.get("origin")
    if _is_allowed_cors_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    return response


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """HTTP exception handler — unified format with CORS headers."""
    body = _build_error_body(
        status_code=exc.status_code,
        detail=str(exc.detail) if exc.detail else "",
        path=str(request.url.path),
    )
    response = JSONResponse(status_code=exc.status_code, content=body)

    origin = request.headers.get("origin")
    if _is_allowed_cors_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"

    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler — unified format with CORS headers."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        logger.error(f"Global exception handler called: {type(exc).__name__}: {exc}", exc_info=True)
    except Exception:
        pass

    error_detail = f"{type(exc).__name__}: {str(exc)}"
    if settings.ENV == "development":
        error_detail += f"\n{traceback.format_exc()}"

    body = _build_error_body(
        status_code=500,
        detail=error_detail,
        path=str(request.url.path),
    )
    response = JSONResponse(status_code=500, content=body)

    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"

    return response


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "B2B Platform API",
        "version": "1.0.0",
        "description": "API for B2B Platform - supplier moderation and parsing system",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "suppliers": "/moderator/suppliers",
            "keywords": "/keywords",
            "blacklist": "/moderator/blacklist",
            "parsing": "/parsing",
            "parsing_runs": "/parsing/runs",
            "domains_queue": "/domains",
            "attachments": "/attachments",
        }
    }

@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint to check route registration."""
    from fastapi.routing import APIRoute
    routes_info = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            if '/parsing/runs' in route.path and 'logs' in route.path:
                routes_info.append({
                    "path": route.path,
                    "methods": list(route.methods),
                    "name": getattr(route, 'name', None),
                    "endpoint": route.endpoint.__name__ if hasattr(route, 'endpoint') else None
                })
    return {"logs_routes": routes_info, "total_routes": len(app.routes)}

@app.get("/debug/all-routes")
async def debug_all_routes():
    """Debug endpoint to check all registered routes."""
    from fastapi.routing import APIRoute
    routes_info = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes_info.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', None),
                "endpoint": route.endpoint.__name__ if hasattr(route, 'endpoint') else None
            })
    # Filter INN extraction routes
    inn_routes = [r for r in routes_info if 'inn' in r['path'].lower()]
    return {
        "total_routes": len(routes_info),
        "inn_routes": inn_routes,
        "all_routes": routes_info
    }


# Include routers
logger.info("Starting router registration")

try:
    logger.info("Registering health router")
    app.include_router(health.router, tags=["Health"])
    
    logger.info("Registering moderator suppliers router")
    app.include_router(moderator_suppliers.router, prefix="/moderator", tags=["Suppliers"])
    
    logger.info("Registering sync workaround router")
    app.include_router(sync_workaround.router, prefix="/test", tags=["Sync Workaround"])

    logger.info("Registering moderator users router")
    app.include_router(moderator_users.router, prefix="/moderator", tags=["Users"])
    
    logger.info("Registering keywords router")
    app.include_router(keywords.router, prefix="/keywords", tags=["Keywords"])
    
    logger.info("Registering blacklist router")
    app.include_router(blacklist.router, prefix="/moderator", tags=["Blacklist"])
    
    logger.info("Registering parsing runs router")
    app.include_router(parsing_runs.router, prefix="/parsing", tags=["Parsing Runs"])
    
    logger.info("Registering parsing router")
    app.include_router(parsing.router, prefix="/parsing", tags=["Parsing"])
    
    logger.info("Registering domains queue router")
    app.include_router(domains_queue.router, prefix="/domains", tags=["Domains Queue"])
    
    logger.info("Registering attachments router")
    app.include_router(attachments.router, prefix="/attachments", tags=["Attachments"])
    
    logger.info("Registering checko router")
    app.include_router(checko.router, prefix="/moderator", tags=["Checko"])
    
    logger.info("Registering domain parser router")
    app.include_router(domain_parser.router, prefix="/domain-parser", tags=["Domain Parser"])
    
    if learning is not None:
        logger.info("Registering learning router")
        app.include_router(learning.router, prefix="/learning", tags=["Learning"])
    
    logger.info("Registering domain_logs router")
    app.include_router(domain_logs.router, prefix="/domain-logs", tags=["Domain Logs"])
    
    logger.info("Registering auth router")
    app.include_router(auth.router, prefix="/api", tags=["Authentication"])

    logger.info("Registering cabinet router")
    app.include_router(cabinet.router, prefix="/cabinet", tags=["Cabinet"])
    
    logger.info("Registering mail router")
    app.include_router(mail.router, prefix="/api", tags=["Mail"])

    logger.info("Registering current task router")
    app.include_router(current_task.router, prefix="/moderator", tags=["Current Task"])
    
    # Log registration summary
    from fastapi.routing import APIRoute
    api_routes = [r for r in app.routes if isinstance(r, APIRoute)]
    logger.info("All routers registered successfully", extra={"app_id": id(app)})
except Exception as e:
    logger.error("Error registering routers", extra={"error": str(e)}, exc_info=True)
    raise

# Final verification after all routers are registered
try:
    from fastapi.routing import APIRoute
    final_routes = [r for r in app.routes if isinstance(r, APIRoute)]
    
    # Check for INN-related routes (checko endpoints)
    inn_routes = [r for r in final_routes if 'checko' in r.path.lower()]
    
    logger.info("Final route verification", extra={
        "total_routes": len(final_routes),
        "inn_checko_routes": len(inn_routes),
        "inn_checko_paths": [r.path for r in inn_routes],
        "app_id": id(app)
    })
    
    if not inn_routes:
        logger.warning("No INN/Checko routes found - this may be expected")
    else:
        logger.info("INN/Checko routes successfully registered")
        
except Exception as e:
    logger.error("Error in final verification", extra={"error": str(e)}, exc_info=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
