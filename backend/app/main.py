"""FastAPI application entry point."""
import sys
import os
import asyncio
import json
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
    auth,
    cabinet,
    mail,
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
            await db.execute(text("ALTER TABLE moderator_suppliers ADD COLUMN IF NOT EXISTS data_status VARCHAR(32) NOT NULL DEFAULT 'complete'"))

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

            # Partial unique index: enforce INN uniqueness unless allow_duplicate_inn=true
            await db.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_suppliers_inn_unique "
                    "ON moderator_suppliers (inn) "
                    "WHERE inn IS NOT NULL AND allow_duplicate_inn = FALSE"
                )
            )

            # Performance indexes for queue/tasks-heavy screens
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

            # Seed domains/emails tables from existing columns (best effort, idempotent).
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

    # Domain parser auto concurrency guard + DB backoff to reduce load spikes.
    try:
        max_concurrency_raw = getattr(settings, "DOMAIN_PARSER_AUTO_MAX_CONCURRENCY", None)
        if max_concurrency_raw is None or str(max_concurrency_raw).strip() == "":
            max_concurrency_raw = os.getenv("DOMAIN_PARSER_AUTO_MAX_CONCURRENCY", "1")
        max_concurrency = max(int(str(max_concurrency_raw).strip() or "1"), 1)
        max_concurrency = min(max_concurrency, 5)
    except Exception:
        max_concurrency = 1
    auto_sem = asyncio.Semaphore(max_concurrency)
    db_fail_streak = 0

    async def _domain_parser_queue_worker() -> None:
        w_logger = get_logger("domain_parser_worker")
        nonlocal db_fail_streak
        while True:
            try:
                try:
                    from app.config import settings as _settings
                    auto_raw = getattr(_settings, "DOMAIN_PARSER_AUTO_ENABLED", None)
                except Exception:
                    auto_raw = None
                if auto_raw is None or str(auto_raw).strip() == "":
                    auto_raw = (os.getenv("DOMAIN_PARSER_AUTO_ENABLED", "1") or "1").strip()
                auto_enabled = str(auto_raw).strip() == "1"
                if not auto_enabled:
                    await asyncio.sleep(10)
                    continue

                try:
                    async with AsyncSessionLocal() as db:
                        # Recovery: ensure every completed run with domains has auto marker.
                        # Older runs (or runs from buggy branches) may miss domain_parser_auto.
                        recover_res = await db.execute(
                            text(
                                "SELECT pr.run_id, pr.process_log "
                                "FROM parsing_runs pr "
                                "WHERE pr.status = 'completed' "
                                "AND COALESCE(pr.process_log->'domain_parser_auto'->>'status','') = '' "
                                "AND EXISTS (SELECT 1 FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id) "
                                "ORDER BY pr.finished_at DESC NULLS LAST, pr.created_at DESC "
                                "LIMIT 20"
                            )
                        )
                        recover_rows = recover_res.fetchall() or []
                        for rec in recover_rows:
                            try:
                                run_id = str(rec[0])
                                pl = rec[1]
                                if isinstance(pl, str):
                                    try:
                                        pl = json.loads(pl)
                                    except Exception:
                                        pl = None
                                if not isinstance(pl, dict):
                                    pl = {}
                                parser_run_id = (
                                    f"auto_parser_recover_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
                                )
                                pl["domain_parser_auto"] = {
                                    "status": "queued",
                                    "parserRunId": parser_run_id,
                                    "mode": "recovery",
                                    "queuedAt": datetime.utcnow().isoformat(),
                                }
                                await db.execute(
                                    text(
                                        "UPDATE parsing_runs "
                                        "SET process_log = CAST(:process_log AS jsonb) "
                                        "WHERE run_id = :run_id"
                                    ),
                                    {"process_log": json.dumps(pl, ensure_ascii=False), "run_id": run_id},
                                )
                            except Exception:
                                w_logger.warning("Failed to enqueue recovery auto parsing marker", exc_info=True)
                        if recover_rows:
                            await db.commit()

                        # Resume: stale auto-enrichment runs stuck in "running" for completed parsing runs.
                        stale_res = await db.execute(
                            text(
                                "SELECT pr.run_id, pr.process_log, pr.finished_at, pr.created_at "
                                "FROM parsing_runs pr "
                                "WHERE pr.status = 'completed' "
                                "AND COALESCE(pr.process_log->'domain_parser_auto'->>'status','') = 'running' "
                                "ORDER BY pr.finished_at DESC NULLS LAST, pr.created_at DESC "
                                "LIMIT 50"
                            )
                        )
                        stale_rows = stale_res.fetchall() or []
                        stale_updated = 0
                        now_utc = datetime.utcnow()
                        for rec in stale_rows:
                            try:
                                run_id = str(rec[0])
                                pl = rec[1]
                                finished_at = rec[2]
                                created_at = rec[3]
                                if isinstance(pl, str):
                                    try:
                                        pl = json.loads(pl)
                                    except Exception:
                                        pl = None
                                if not isinstance(pl, dict):
                                    continue
                                dp = pl.get("domain_parser_auto")
                                if not isinstance(dp, dict):
                                    continue
                                # Skip active in-memory parser runs.
                                parser_run_id = str(dp.get("parserRunId") or "").strip()
                                in_memory = None
                                if parser_run_id:
                                    try:
                                        in_memory = domain_parser._parser_runs.get(parser_run_id)
                                    except Exception:
                                        in_memory = None
                                if isinstance(in_memory, dict) and str(in_memory.get("status") or "") == "running":
                                    continue

                                # Consider stale when run finished/created long ago and no finishedAt in auto block.
                                pivot = finished_at or created_at
                                if not pivot:
                                    continue
                                age_sec = (now_utc - pivot.replace(tzinfo=None)).total_seconds()
                                if age_sec < 300:  # 5 minutes grace window
                                    continue
                                if dp.get("finishedAt"):
                                    continue

                                dp["status"] = "queued"
                                dp["queuedAt"] = datetime.utcnow().isoformat()
                                dp["resumedAt"] = datetime.utcnow().isoformat()
                                dp["resumeReason"] = "stalled_recovered"
                                dp["processed"] = int(dp.get("processed") or 0)
                                dp["total"] = int(dp.get("total") or dp.get("domains") or 0)
                                pl["domain_parser_auto"] = dp
                                await db.execute(
                                    text(
                                        "UPDATE parsing_runs "
                                        "SET process_log = CAST(:process_log AS jsonb) "
                                        "WHERE run_id = :run_id"
                                    ),
                                    {"process_log": json.dumps(pl, ensure_ascii=False), "run_id": run_id},
                                )
                                stale_updated += 1
                            except Exception:
                                w_logger.warning("Failed to requeue stale running auto marker", exc_info=True)
                        if stale_updated:
                            await db.commit()
                            w_logger.warning("Re-queued stale domain_parser_auto for resume: %s run(s)", stale_updated)

                        # Recovery for previously marked failed-but-resumable auto runs.
                        failed_res = await db.execute(
                            text(
                                "SELECT pr.run_id, pr.process_log "
                                "FROM parsing_runs pr "
                                "WHERE pr.status = 'completed' "
                                "AND COALESCE(pr.process_log->'domain_parser_auto'->>'status','') = 'failed' "
                                "ORDER BY pr.finished_at DESC NULLS LAST, pr.created_at DESC "
                                "LIMIT 50"
                            )
                        )
                        failed_rows = failed_res.fetchall() or []
                        failed_requeued = 0
                        for rec in failed_rows:
                            try:
                                run_id = str(rec[0])
                                pl = rec[1]
                                if isinstance(pl, str):
                                    try:
                                        pl = json.loads(pl)
                                    except Exception:
                                        pl = None
                                if not isinstance(pl, dict):
                                    continue
                                dp = pl.get("domain_parser_auto")
                                if not isinstance(dp, dict):
                                    continue
                                processed = int(dp.get("processed") or 0)
                                total = int(dp.get("total") or dp.get("domains") or 0)
                                if total <= 0 or processed >= total:
                                    continue
                                if str(dp.get("resumeReason") or "") == "stalled_recovered":
                                    continue
                                dp["status"] = "queued"
                                dp["queuedAt"] = datetime.utcnow().isoformat()
                                dp["resumedAt"] = datetime.utcnow().isoformat()
                                dp["resumeReason"] = "failed_recovered"
                                pl["domain_parser_auto"] = dp
                                await db.execute(
                                    text(
                                        "UPDATE parsing_runs "
                                        "SET process_log = CAST(:process_log AS jsonb) "
                                        "WHERE run_id = :run_id"
                                    ),
                                    {"process_log": json.dumps(pl, ensure_ascii=False), "run_id": run_id},
                                )
                                failed_requeued += 1
                            except Exception:
                                w_logger.warning("Failed to requeue failed auto marker", exc_info=True)
                        if failed_requeued:
                            await db.commit()
                            w_logger.warning("Re-queued failed/resumable domain_parser_auto: %s run(s)", failed_requeued)

                        # Recovery for inconsistent completed markers with unfinished progress.
                        inconsistent_res = await db.execute(
                            text(
                                "SELECT pr.run_id, pr.process_log "
                                "FROM parsing_runs pr "
                                "WHERE pr.status = 'completed' "
                                "AND COALESCE(pr.process_log->'domain_parser_auto'->>'status','') = 'completed' "
                                "ORDER BY pr.finished_at DESC NULLS LAST, pr.created_at DESC "
                                "LIMIT 100"
                            )
                        )
                        inconsistent_rows = inconsistent_res.fetchall() or []
                        inconsistent_requeued = 0
                        for rec in inconsistent_rows:
                            try:
                                run_id = str(rec[0])
                                pl = rec[1]
                                if isinstance(pl, str):
                                    try:
                                        pl = json.loads(pl)
                                    except Exception:
                                        pl = None
                                if not isinstance(pl, dict):
                                    continue
                                dp = pl.get("domain_parser_auto")
                                if not isinstance(dp, dict):
                                    continue
                                processed = int(dp.get("processed") or 0)
                                total = int(dp.get("total") or dp.get("domains") or 0)
                                skipped_existing = int(dp.get("skippedExisting") or 0)
                                if total <= 0:
                                    continue
                                if (processed + skipped_existing) >= total:
                                    continue
                                dp["status"] = "queued"
                                dp["queuedAt"] = datetime.utcnow().isoformat()
                                dp["resumedAt"] = datetime.utcnow().isoformat()
                                dp["resumeReason"] = "incomplete_completed_recovered"
                                dp.pop("finishedAt", None)
                                pl["domain_parser_auto"] = dp
                                await db.execute(
                                    text(
                                        "UPDATE parsing_runs "
                                        "SET process_log = CAST(:process_log AS jsonb) "
                                        "WHERE run_id = :run_id"
                                    ),
                                    {"process_log": json.dumps(pl, ensure_ascii=False), "run_id": run_id},
                                )
                                inconsistent_requeued += 1
                            except Exception:
                                w_logger.warning("Failed to requeue inconsistent completed auto marker", exc_info=True)
                        if inconsistent_requeued:
                            await db.commit()
                            w_logger.warning(
                                "Re-queued inconsistent completed domain_parser_auto: %s run(s)",
                                inconsistent_requeued,
                            )

                        res = await db.execute(
                            text(
                                "SELECT run_id, process_log "
                                "FROM parsing_runs "
                                "WHERE COALESCE(process_log->'domain_parser_auto'->>'status','') = 'queued' "
                                "ORDER BY created_at ASC "
                                "LIMIT 10"
                            )
                        )
                        rows = res.fetchall() or []
                    db_fail_streak = 0
                except Exception as e:
                    db_fail_streak += 1
                    backoff = min(60, 2 ** min(db_fail_streak, 5))
                    w_logger.warning(
                        "Domain parser worker DB error: %s (backing off %ss)",
                        str(e),
                        backoff,
                        exc_info=True,
                    )
                    await asyncio.sleep(backoff)
                    continue

                for row in rows:
                    if auto_sem.locked():
                        break
                    permit_acquired = False
                    try:
                        run_id = str(row[0])
                        pl = row[1]
                        if isinstance(pl, str):
                            try:
                                pl = json.loads(pl)
                            except Exception:
                                pl = None
                        if not isinstance(pl, dict):
                            pl = {}
                        dp = pl.get("domain_parser_auto")
                        if not isinstance(dp, dict):
                            continue
                        parser_run_id = str(dp.get("parserRunId") or "").strip()
                        if not parser_run_id:
                            continue

                        async with AsyncSessionLocal() as db:
                            dq_res = await db.execute(
                                text(
                                    "SELECT DISTINCT domain "
                                    "FROM domains_queue "
                                    "WHERE parsing_run_id = :run_id "
                                    "ORDER BY domain ASC"
                                ),
                                {"run_id": run_id},
                            )
                            all_domains = [str(x[0]).strip() for x in (dq_res.fetchall() or []) if x and x[0]]
                            domains = list(all_domains)
                            total_all_domains = len(all_domains)

                            # Resume from where it stopped: skip already processed domains for this parserRunId.
                            try:
                                def _norm(d: str) -> str:
                                    s = str(d or "").strip().lower()
                                    if s.startswith("www."):
                                        s = s[4:]
                                    return s

                                processed_set: set[str] = set()
                                dpr = (
                                    (pl.get("domain_parser") or {}).get("runs", {}).get(parser_run_id, {})
                                    if isinstance(pl.get("domain_parser"), dict)
                                    else {}
                                )
                                dpr_results = dpr.get("results") if isinstance(dpr, dict) else []
                                if isinstance(dpr_results, list):
                                    for rr in dpr_results:
                                        if isinstance(rr, dict):
                                            dd = _norm(str(rr.get("domain") or ""))
                                            if dd:
                                                processed_set.add(dd)
                                if processed_set:
                                    domains = [d for d in domains if _norm(d) not in processed_set]
                            except Exception:
                                pass

                            # Limit batch size to avoid overloading the machine.
                            try:
                                limit_raw = (os.getenv("DOMAIN_PARSER_AUTO_LIMIT", "3") or "3").strip()
                                limit_n = max(int(limit_raw), 1)
                            except Exception:
                                limit_n = 3
                            if len(domains) > limit_n:
                                domains = domains[:limit_n]

                            if not domains:
                                dp["status"] = "completed"
                                dp["finishedAt"] = datetime.utcnow().isoformat()
                                dp["total"] = int(total_all_domains)
                                dp["processed"] = int(total_all_domains)
                                pl["domain_parser_auto"] = dp
                                await db.execute(
                                    text(
                                        "UPDATE parsing_runs "
                                        "SET process_log = CAST(:process_log AS jsonb) "
                                        "WHERE run_id = :run_id"
                                    ),
                                    {
                                        "process_log": json.dumps(pl, ensure_ascii=False),
                                        "run_id": run_id,
                                    },
                                )
                                await db.commit()
                                continue

                            if auto_sem.locked():
                                break
                            await auto_sem.acquire()
                            permit_acquired = True

                            dp["status"] = "running"
                            dp["pickedAt"] = datetime.utcnow().isoformat()
                            dp["domains"] = int(total_all_domains)
                            dp["total"] = int(total_all_domains)
                            pl["domain_parser_auto"] = dp
                            await db.execute(
                                text(
                                    "UPDATE parsing_runs "
                                    "SET process_log = CAST(:process_log AS jsonb) "
                                    "WHERE run_id = :run_id"
                                ),
                                {
                                    "process_log": json.dumps(pl, ensure_ascii=False),
                                    "run_id": run_id,
                                },
                            )
                            await db.commit()

                        try:
                            domain_parser._parser_runs[parser_run_id] = {
                                "runId": run_id,
                                "parserRunId": parser_run_id,
                                "status": "running",
                                "processed": int(dp.get("processed") or 0),
                                "total": int(total_all_domains),
                                "baseProcessed": int(dp.get("processed") or 0),
                                "overallTotal": int(total_all_domains),
                                "currentDomain": None,
                                "currentSourceUrls": [],
                                "results": [],
                                "startedAt": datetime.utcnow().isoformat(),
                                "auto": True,
                            }
                        except Exception:
                            pass

                        async def _run_and_mark() -> None:
                            try:
                                await domain_parser._process_domain_parser_batch(parser_run_id, run_id, domains)
                                status_val = "completed"
                                err_val = None
                            except Exception as e:
                                status_val = "failed"
                                err_val = str(e)[:800]

                            try:
                                run_state = domain_parser._parser_runs.get(parser_run_id) or {}
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
                                    dp2 = pl2.get("domain_parser_auto")
                                    if isinstance(dp2, dict) and str(dp2.get("parserRunId") or "") == parser_run_id:
                                        processed_now = int(run_state.get("processed") or dp2.get("processed") or 0)
                                        total_now = int(run_state.get("total") or dp2.get("total") or len(domains))
                                        # If only a limited auto-batch was processed, keep run queued until fully done.
                                        if status_val == "completed" and processed_now < total_now:
                                            status_val = "queued"
                                            dp2["queuedAt"] = datetime.utcnow().isoformat()
                                        dp2["status"] = status_val
                                        dp2["processed"] = processed_now
                                        dp2["total"] = total_now
                                        if err_val:
                                            dp2["error"] = err_val
                                        if status_val in {"completed", "failed"}:
                                            dp2["finishedAt"] = datetime.utcnow().isoformat()
                                        else:
                                            dp2.pop("finishedAt", None)
                                        pl2["domain_parser_auto"] = dp2
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
                            finally:
                                try:
                                    auto_sem.release()
                                except Exception:
                                    pass

                        asyncio.create_task(_run_and_mark())
                        w_logger.info(
                            "Picked queued domain_parser_auto for run_id=%s parserRunId=%s domains=%s",
                            run_id,
                            parser_run_id,
                            len(domains),
                        )
                    except Exception as e:
                        w_logger.warning("Failed to pick queued domain_parser_auto: %s", str(e), exc_info=True)
                        if permit_acquired:
                            try:
                                auto_sem.release()
                            except Exception:
                                pass
            except Exception as e:
                w_logger.warning("Domain parser worker tick failed: %s", str(e), exc_info=True)

            await asyncio.sleep(10)

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
    """Starlette-level exception handler."""
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
        content={"detail": error_detail}
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

# CORS Middleware - должен быть первым
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Ngrok bypass middleware - добавляем заголовки для обхода ngrok warning
class NgrokBypassMiddleware(BaseHTTPMiddleware):
    """Middleware to bypass ngrok browser warning by adding required headers."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Добавляем заголовки для обхода ngrok warning ко всем ответам
        response.headers["ngrok-skip-browser-warning"] = "true"
        
        return response

app.add_middleware(NgrokBypassMiddleware)

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
            if origin and origin in settings.cors_origins_list:
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
                content={"detail": error_detail}
            )
            
            origin = request.headers.get("origin")
            if origin and origin in settings.cors_origins_list:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "*"
                response.headers["Access-Control-Allow-Headers"] = "*"
            
            return response

app.add_middleware(CORSExceptionMiddleware)

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

app.add_middleware(NgrokWarningMiddleware)

# Global exception handler for debugging - ДОЛЖЕН быть ДО включения роутеров!
from fastapi.exceptions import HTTPException as FastAPIHTTPException

@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """HTTP exception handler with CORS headers."""
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    
    # Add CORS headers manually
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to log errors and return details with CORS headers."""
    import logging
    logger = logging.getLogger(__name__)
    # Безопасное логирование - оборачиваем в try-except
    try:
        logger.error(f"Global exception handler called: {type(exc).__name__}: {exc}", exc_info=True)
    except Exception:
        pass  # Если логирование не работает, просто пропускаем
    
    error_detail = f"{type(exc).__name__}: {str(exc)}"
    if settings.ENV == "development":
        error_detail += f"\n{traceback.format_exc()}"
    
    # Create response with CORS headers
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": error_detail}
    )
    
    # Add CORS headers manually
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
    
    logger.info("Registering auth router")
    app.include_router(auth.router, prefix="/api", tags=["Authentication"])

    logger.info("Registering cabinet router")
    app.include_router(cabinet.router, prefix="/cabinet", tags=["Cabinet"])
    
    logger.info("Registering mail router")
    app.include_router(mail.router, prefix="/api", tags=["Mail"])
    
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
