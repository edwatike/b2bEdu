"""Domain Parser API router."""
import asyncio
import logging
import uuid
import json
from datetime import datetime
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.session import get_db
from app.transport.routers.auth import get_current_user
from app.utils.authz import require_moderator
from app.utils.rate_limit import limiter, DOMAIN_PARSER_LIMIT
from app.transport.schemas.domain_parser import (
    DomainParserRequestDTO,
    DomainParserBatchResponseDTO,
    DomainParserStatusResponseDTO
)
from app.usecases import get_parsing_run
from app.utils.domain import normalize_domain_root

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for parser runs status
_parser_runs: Dict[str, Dict] = {}

# ---------------------------------------------------------------------------
# Global in-process DomainInfoParser (reuses a single browser across domains)
# ---------------------------------------------------------------------------
import os as _os
import sys as _sys

_domain_parser_dir = _os.path.normpath(
    _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "..", "domain_info_parser")
)
if _domain_parser_dir not in _sys.path:
    _sys.path.insert(0, _domain_parser_dir)

_inprocess_parser = None  # will hold DomainInfoParser instance
_inprocess_lock = asyncio.Lock()  # serialise browser access


async def _get_inprocess_parser():
    """Return (and lazily create) a long-lived DomainInfoParser instance."""
    global _inprocess_parser
    async with _inprocess_lock:
        if _inprocess_parser is not None and _inprocess_parser.browser is not None:
            # Check browser is still alive
            try:
                if _inprocess_parser.browser.is_connected():
                    return _inprocess_parser
            except Exception:
                pass
            # Browser died – recreate
            try:
                await _inprocess_parser.close()
            except Exception:
                pass
            _inprocess_parser = None

        try:
            import sys, os
            _dip = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), '..', 'domain_info_parser')
            _dip = os.path.normpath(_dip)
            if _dip not in sys.path:
                sys.path.insert(0, _dip)
            from parser import DomainInfoParser  # noqa: from domain_info_parser/parser.py
            p = DomainInfoParser(headless=True, timeout=12000)
            await p.start()
            _inprocess_parser = p
            logger.info("In-process DomainInfoParser started (browser reused across domains)")
            return _inprocess_parser
        except Exception as e:
            logger.error("Failed to start in-process DomainInfoParser: %s", e, exc_info=True)
            raise

# Global pause flag for domain parser auto worker.
# When True the queue worker in main.py skips picking new runs and
# _process_domain_parser_batch stops after the current domain finishes
# WITHOUT marking it as requires_moderation.
_worker_paused: bool = False


@router.get("/moderation-domains")
async def list_moderation_domains(
    limit: int = 5000,
    current_user: dict = Depends(get_current_user),
):
    """List globally blocked domains that require moderation."""
    require_moderator(current_user)
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            text(
                "SELECT domain FROM domain_moderation "
                "WHERE COALESCE(status, 'requires_moderation') = 'requires_moderation' "
                "ORDER BY created_at DESC "
                "LIMIT :limit"
            ),
            {"limit": int(max(1, min(limit, 20000)))},
        )
        domains = [str(r[0]) for r in (res.fetchall() or []) if r and r[0]]
    return {"domains": domains, "total": len(domains)}


@router.post("/pause")
async def pause_worker(
    current_user: dict = Depends(get_current_user),
):
    """Pause the domain parser auto worker globally.

    The worker will finish the domain it is currently processing and then stop.
    The domain being processed when pause is requested will NOT be marked as
    ``requires_moderation`` — it will be retried on resume.
    """
    global _worker_paused
    require_moderator(current_user)
    _worker_paused = True
    logger.info("Domain parser auto worker PAUSED by user %s", current_user.get("username"))
    return {"paused": True, "message": "Worker paused. Current domain will finish, then stop."}


@router.post("/resume")
async def resume_worker(
    current_user: dict = Depends(get_current_user),
):
    """Resume the domain parser auto worker after a pause."""
    global _worker_paused
    require_moderator(current_user)
    _worker_paused = False
    logger.info("Domain parser auto worker RESUMED by user %s", current_user.get("username"))
    return {"paused": False, "message": "Worker resumed. Will continue from where it stopped."}


@router.get("/worker-status")
async def get_worker_status(
    current_user: dict = Depends(get_current_user),
):
    """Get the current status of the domain parser auto worker."""
    require_moderator(current_user)

    # Find the currently running parser run (if any)
    current_run = None
    for pid, pdata in _parser_runs.items():
        if pdata.get("status") == "running":
            current_run = {
                "parserRunId": pid,
                "runId": pdata.get("runId"),
                "keyword": pdata.get("keyword", ""),
                "processed": pdata.get("processed", 0),
                "total": pdata.get("total", 0),
                "currentDomain": pdata.get("currentDomain"),
                "currentSourceUrls": pdata.get("currentSourceUrls", []),
                "startedAt": pdata.get("startedAt"),
            }
            break

    return {
        "paused": _worker_paused,
        "currentRun": current_run,
    }


def _normalize_domain_full(domain: str) -> str:
    """Normalize domain for exact matching: lowercase, strip www., protocol, path."""
    d = str(domain).strip().lower()
    if not d:
        return ""
    if "://" in d:
        try:
            from urllib.parse import urlparse
            d = urlparse(d).netloc or d
        except Exception:
            pass
    d = d.split("/")[0].strip()
    if d.startswith("www."):
        d = d[4:]
    return d


async def _domain_exists_in_suppliers(domain: str) -> bool:
    """Check whether domain (or its root) is already present in moderator_suppliers/supplier_domains.

    Checks both full domain (spb.lemanapro.ru) AND root domain (lemanapro.ru).
    If either matches — the domain is considered processed.
    """
    full = _normalize_domain_full(domain)
    if not full:
        return False
    root = _normalize_domain(domain)
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    candidates = list({full, root} - {""})
    async with AsyncSessionLocal() as db:
        for d in candidates:
            res = await db.execute(
                text(
                    "SELECT 1 "
                    "FROM moderator_suppliers ms "
                    "LEFT JOIN supplier_domains sd ON sd.supplier_id = ms.id "
                    "WHERE replace(lower(COALESCE(sd.domain, ms.domain, '')), 'www.', '') = :d "
                    "LIMIT 1"
                ),
                {"d": d},
            )
            if res.fetchone() is not None:
                return True
    return False


async def _domain_requires_moderation(domain: str) -> bool:
    full = _normalize_domain_full(domain)
    if not full:
        return False
    root = _normalize_domain(domain)
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    candidates = list({full, root} - {""})
    async with AsyncSessionLocal() as db:
        for d in candidates:
            res = await db.execute(
                text(
                    "SELECT 1 FROM domain_moderation "
                    "WHERE replace(lower(domain), 'www.', '') = :d "
                    "AND COALESCE(status, 'requires_moderation') = 'requires_moderation' "
                    "LIMIT 1"
                ),
                {"d": d},
            )
            if res.fetchone() is not None:
                return True
    return False


async def _get_domain_moderation_reason(domain: str) -> str | None:
    full = _normalize_domain_full(domain)
    if not full:
        return None
    root = _normalize_domain(domain)
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    candidates = list({full, root} - {""})
    async with AsyncSessionLocal() as db:
        for d in candidates:
            res = await db.execute(
                text(
                    "SELECT reason FROM domain_moderation "
                    "WHERE replace(lower(domain), 'www.', '') = :d "
                    "AND COALESCE(status, 'requires_moderation') = 'requires_moderation' "
                    "LIMIT 1"
                ),
                {"d": d},
            )
            row = res.fetchone()
            if row is not None:
                return str(row[0]) if row[0] is not None else None
    return None


async def _mark_domain_requires_moderation(domain: str, reason: str = "inn_not_found") -> None:
    norm = _normalize_domain(domain)
    if not norm:
        return
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "INSERT INTO domain_moderation (domain, status, reason) "
                "VALUES (:d, 'requires_moderation', :reason) "
                "ON CONFLICT (domain) DO UPDATE SET "
                "status='requires_moderation', reason=EXCLUDED.reason"
            ),
            {"d": norm, "reason": reason[:200]},
        )
        await db.commit()


async def _sync_domain_parser_auto_progress(
    *,
    run_id: str,
    parser_run_id: str,
    processed: int,
    total: int,
    status: str | None = None,
    last_domain: str | None = None,
    error: str | None = None,
) -> None:
    """Persist live auto-enrichment progress into parsing_runs.process_log.domain_parser_auto."""
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
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
            if str(dp.get("parserRunId") or "") != str(parser_run_id):
                return
            dp["processed"] = int(processed)
            dp["total"] = int(total)
            if status:
                dp["status"] = str(status)
            if last_domain:
                dp["lastDomain"] = str(last_domain)
            if error:
                dp["error"] = str(error)[:800]
            if status in {"completed", "failed"}:
                dp["finishedAt"] = datetime.now().isoformat()
            pl["domain_parser_auto"] = dp
            await db.execute(
                text("UPDATE parsing_runs SET process_log = CAST(:process_log AS jsonb) WHERE run_id = :run_id"),
                {"process_log": json.dumps(pl, ensure_ascii=False), "run_id": run_id},
            )
            await db.commit()
    except Exception:
        logger.warning("Failed to sync domain_parser_auto progress for run_id=%s", run_id, exc_info=True)


def _normalize_domain(domain: str) -> str:
    return normalize_domain_root(domain)


async def _sync_run_domain_status(
    *,
    run_id: str,
    domain: str,
    status: str,
    reason: str | None = None,
    attempted_urls: object | None = None,
    inn_source_url: str | None = None,
    email_source_url: str | None = None,
    supplier_id: int | None = None,
    checko_ok: bool = False,
    global_requires_moderation: bool = False,
) -> None:
    """Upsert a run_domains row to track per-run domain enrichment status."""
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    norm = _normalize_domain(domain)
    if not norm:
        return
    try:
        # Write persistent domain log (separate session to avoid tx conflicts)
        try:
            from app.transport.routers.domain_logs import write_log, ensure_table
            async with AsyncSessionLocal() as log_db:
                await ensure_table(log_db)
                await write_log(
                    log_db, norm, status,
                    message=reason,
                    run_id=run_id,
                    details={"inn_source_url": inn_source_url, "email_source_url": email_source_url,
                             "supplier_id": supplier_id, "checko_ok": checko_ok},
                )
        except Exception:
            pass  # logging must never break main flow
        async with AsyncSessionLocal() as db:
            try:
                urls_payload = json.dumps(attempted_urls if attempted_urls is not None else [])
            except Exception:
                urls_payload = json.dumps([])
            await db.execute(
                text(
                    "INSERT INTO run_domains "
                    "(run_id, domain, status, reason, attempted_urls, "
                    " inn_source_url, email_source_url, supplier_id, checko_ok, "
                    " global_requires_moderation) "
                    "VALUES (:run_id, :domain, :status, :reason, "
                    " CAST(:urls AS jsonb), :inn_url, :email_url, :sid, :checko, :grm) "
                    "ON CONFLICT (run_id, domain) DO UPDATE SET "
                    " status = EXCLUDED.status, "
                    " reason = EXCLUDED.reason, "
                    " attempted_urls = COALESCE(EXCLUDED.attempted_urls, run_domains.attempted_urls), "
                    " inn_source_url = COALESCE(EXCLUDED.inn_source_url, run_domains.inn_source_url), "
                    " email_source_url = COALESCE(EXCLUDED.email_source_url, run_domains.email_source_url), "
                    " supplier_id = COALESCE(EXCLUDED.supplier_id, run_domains.supplier_id), "
                    " checko_ok = EXCLUDED.checko_ok, "
                    " global_requires_moderation = EXCLUDED.global_requires_moderation, "
                    " updated_at = NOW()"
                ),
                {
                    "run_id": run_id,
                    "domain": norm,
                    "status": status,
                    "reason": (reason or "")[:500] if reason else None,
                    "urls": urls_payload,
                    "inn_url": inn_source_url,
                    "email_url": email_source_url,
                    "sid": supplier_id,
                    "checko": checko_ok,
                    "grm": global_requires_moderation,
                },
            )
            await db.commit()
    except Exception:
        logger.warning("Failed to sync run_domain status for %s / %s", run_id, norm, exc_info=True)


async def _get_run_domain_attempted_urls(run_id: str, domain: str) -> object | None:
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    norm = _normalize_domain(domain)
    if not norm:
        return None
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                text(
                    "SELECT attempted_urls FROM run_domains "
                    "WHERE run_id = :run_id AND domain = :domain "
                    "LIMIT 1"
                ),
                {"run_id": str(run_id), "domain": str(norm)},
            )
            row = res.fetchone()
            if not row:
                return None
            return row[0]
    except Exception:
        return None


@router.post("/extract-batch", response_model=DomainParserBatchResponseDTO)
@limiter.limit(DOMAIN_PARSER_LIMIT)
async def start_domain_parser_batch(
    request: Request,
    body: DomainParserRequestDTO,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Start batch domain parsing for INN and email extraction."""
    require_moderator(current_user)
    run_id = body.runId
    domains = body.domains
    force = bool(getattr(body, "force", False))
    
    logger.info(f"=== DOMAIN PARSER BATCH START ===")
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Domains: {len(domains)}")
    
    try:
        # Verify parsing run exists
        parsing_run = await get_parsing_run.execute(db=db, run_id=run_id)
        if not parsing_run:
            raise HTTPException(status_code=404, detail="Parsing run not found")
        
        # Generate unique parser run ID
        parser_run_id = f"parser_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Initialize status
        _parser_runs[parser_run_id] = {
            "runId": run_id,
            "parserRunId": parser_run_id,
            "status": "running",
            "processed": 0,
            "total": len(domains),
            "currentDomain": None,
            "currentSourceUrls": [],
            "results": [],
            "startedAt": datetime.now().isoformat(),
            "force": force,
        }
        
        # Start background task
        background_tasks.add_task(_process_domain_parser_batch, parser_run_id, run_id, domains, force)
        
        logger.info(f"Domain parser batch started: {parser_run_id}")
        
        return DomainParserBatchResponseDTO(
            runId=run_id,
            parserRunId=parser_run_id
        )
        
    except Exception as e:
        logger.error(f"Error starting domain parser batch: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/status/{parserRunId}", response_model=DomainParserStatusResponseDTO)
async def get_domain_parser_status(
    parserRunId: str,
    current_user: dict = Depends(get_current_user),
):
    """Get status of domain parser run.

    First checks in-memory ``_parser_runs`` dict (live data with currentDomain /
    currentSourceUrls).  If not found (e.g. after backend restart), falls back to
    ``parsing_runs.process_log.domain_parser_auto`` in the database so the frontend
    never gets a 404 for a legitimately started auto-enrichment run.
    """
    require_moderator(current_user)

    # 1. Fast path: in-memory (live progress with currentDomain / sourceUrls)
    if parserRunId in _parser_runs:
        run_data = _parser_runs[parserRunId]
        return DomainParserStatusResponseDTO(
            runId=run_data["runId"],
            parserRunId=run_data["parserRunId"],
            status=run_data["status"],
            processed=run_data["processed"],
            total=run_data["total"],
            currentDomain=run_data.get("currentDomain"),
            currentSourceUrls=run_data.get("currentSourceUrls", []) or [],
            results=run_data.get("results", []),
        )

    # 2. Slow path: reconstruct from DB process_log
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                text(
                    "SELECT run_id, process_log FROM parsing_runs "
                    "WHERE process_log->'domain_parser_auto'->>'parserRunId' = :prid "
                    "LIMIT 1"
                ),
                {"prid": str(parserRunId)},
            )
            row = res.fetchone()
            if not row:
                # Also check parserRunIds array (batch mode stores multiple ids)
                res2 = await db.execute(
                    text(
                        "SELECT run_id, process_log FROM parsing_runs "
                        "WHERE process_log->'domain_parser_auto'->'parserRunIds' @> CAST(:prid_json AS jsonb) "
                        "LIMIT 1"
                    ),
                    {"prid_json": json.dumps([str(parserRunId)])},
                )
                row = res2.fetchone()

            if not row:
                # Also check legacy/batch domain_parser log: process_log.domain_parser.runs.<parserRunId>
                # This is where some UI paths still take parserRunId from.
                res3 = await db.execute(
                    text(
                        "SELECT run_id, process_log FROM parsing_runs "
                        "WHERE (process_log->'domain_parser'->'runs' ? :prid) "
                        "LIMIT 1"
                    ),
                    {"prid": str(parserRunId)},
                )
                row = res3.fetchone()

            if row:
                run_id = str(row[0])
                pl = row[1]
                if isinstance(pl, str):
                    try:
                        pl = json.loads(pl)
                    except Exception:
                        pl = {}
                if not isinstance(pl, dict):
                    pl = {}
                dp = pl.get("domain_parser_auto") or {}

                # If dpAuto doesn't match, fall back to process_log.domain_parser.runs[parserRunId]
                dp_status = dp
                try:
                    if str(dp.get("parserRunId") or "") != str(parserRunId):
                        runs = ((pl.get("domain_parser") or {}).get("runs") or {})
                        if isinstance(runs, dict) and str(parserRunId) in runs and isinstance(runs.get(str(parserRunId)), dict):
                            dp_status = runs.get(str(parserRunId)) or {}
                except Exception:
                    dp_status = dp

                db_results: list[dict] = []
                try:
                    res_rd = await db.execute(
                        text(
                            "SELECT domain, status, reason, attempted_urls, inn_source_url, email_source_url "
                            "FROM run_domains WHERE run_id = :run_id "
                            "ORDER BY updated_at DESC"
                        ),
                        {"run_id": str(run_id)},
                    )
                    for d, st, rsn, au, inn_url, email_url in (res_rd.fetchall() or []):
                        attempted = au
                        inn_val = None
                        emails_val: list[str] = []
                        src_urls: list[str] = []
                        extraction_log: list = []
                        err_val = None
                        learned_val = False
                        prev_inn = None
                        prev_emails: list[str] = []
                        strategy_used = None
                        strategy_time_ms = None
                        if isinstance(attempted, dict):
                            inn_val = attempted.get("inn")
                            emails_val = attempted.get("emails") or []
                            src_urls = attempted.get("sourceUrls") or []
                            extraction_log = attempted.get("extractionLog") or []
                            err_val = attempted.get("error")
                            learned_val = bool(attempted.get("learned"))
                            strategy_used = attempted.get("strategyUsed")
                            strategy_time_ms = attempted.get("strategyTimeMs")
                            prev = attempted.get("previous")
                            if isinstance(prev, dict):
                                prev_inn = prev.get("inn")
                                prev_emails = prev.get("emails") or []
                        elif isinstance(attempted, list):
                            src_urls = attempted

                        db_results.append(
                            {
                                "domain": str(d),
                                "inn": inn_val,
                                "emails": emails_val,
                                "sourceUrls": src_urls,
                                "extractionLog": extraction_log,
                                "error": err_val or (str(rsn) if str(st) == "requires_moderation" and rsn else None),
                                "learned": learned_val,
                                "previousInn": prev_inn,
                                "previousEmails": prev_emails,
                                "innSourceUrl": inn_url,
                                "emailSourceUrl": email_url,
                                "status": str(st) if st is not None else None,
                                "reason": str(rsn) if rsn is not None else None,
                                "strategyUsed": strategy_used,
                                "strategyTimeMs": strategy_time_ms,
                            }
                        )
                except Exception:
                    db_results = []

                return DomainParserStatusResponseDTO(
                    runId=run_id,
                    parserRunId=str(dp_status.get("parserRunId") or dp.get("parserRunId") or parserRunId),
                    status=str(dp_status.get("status") or "completed"),
                    processed=int(dp_status.get("processed") or dp.get("processed") or 0),
                    total=int(dp_status.get("total") or dp_status.get("domains") or dp.get("total") or dp.get("domains") or 0),
                    currentDomain=str(dp_status.get("currentDomain") or dp_status.get("lastDomain") or dp.get("lastDomain") or "") or None,
                    currentSourceUrls=[],
                    results=db_results,
                )
    except Exception:
        logger.warning("DB fallback for domain parser status failed", exc_info=True)

    raise HTTPException(status_code=404, detail="Parser run not found")


async def _process_domain_parser_batch(parser_run_id: str, run_id: str, domains: List[str], force: bool = False):
    """Background task to process domain parser batch."""
    logger.info(f"=== PROCESSING DOMAIN PARSER BATCH ===")
    logger.info(f"Parser Run ID: {parser_run_id}")
    logger.info(f"Domains: {len(domains)}")
    
    results = []
    
    try:
        base_processed = int(_parser_runs.get(parser_run_id, {}).get("baseProcessed") or 0)
        overall_total = int(_parser_runs.get(parser_run_id, {}).get("overallTotal") or len(domains))
        paused_early = False
        for i, domain in enumerate(domains):
            # --- PAUSE CHECK (before starting a new domain) ---
            if _worker_paused:
                logger.info(
                    "Domain parser auto worker PAUSED before domain %s (%d/%d) — stopping batch",
                    domain, i + 1, len(domains),
                )
                paused_early = True
                break

            logger.info(f"Processing domain {i+1}/{len(domains)}: {domain}")
            _parser_runs[parser_run_id]["currentDomain"] = _normalize_domain(domain)
            _parser_runs[parser_run_id]["currentSourceUrls"] = []

            # Mark domain as processing in run_domains
            try:
                await _sync_run_domain_status(run_id=run_id, domain=domain, status="processing")
            except Exception:
                pass
            
            try:
                # Optimization: if domain already exists as a supplier, skip heavy parsing/enrichment.
                if await _domain_exists_in_suppliers(domain):
                    result = {
                        "domain": _normalize_domain(domain),
                        "inn": None,
                        "emails": [],
                        "sourceUrls": [],
                        "error": None,
                        "skipped": True,
                        "reason": "supplier_exists",
                    }
                    # Mark as supplier in run_domains (already processed)
                    try:
                        await _sync_run_domain_status(run_id=run_id, domain=domain, status="supplier")
                    except Exception:
                        pass
                elif (not force) and await _domain_requires_moderation(domain):
                    mod_reason = None
                    try:
                        mod_reason = await _get_domain_moderation_reason(domain)
                    except Exception:
                        mod_reason = None
                    result = {
                        "domain": _normalize_domain(domain),
                        "inn": None,
                        "emails": [],
                        "sourceUrls": [],
                        "error": None,
                        "skipped": True,
                        "reason": "requires_moderation",
                    }
                    # Mark as requires_moderation with global flag in run_domains
                    try:
                        await _sync_run_domain_status(
                            run_id=run_id, domain=domain,
                            status="requires_moderation",
                            reason=mod_reason,
                            global_requires_moderation=True,
                        )
                    except Exception:
                        pass
                else:
                    result = await _run_domain_parser_for_domain(domain)
                try:
                    result["domain"] = _normalize_domain(result.get("domain") or domain)
                except Exception:
                    pass
                _parser_runs[parser_run_id]["currentSourceUrls"] = list(result.get("sourceUrls") or [])
                results.append(result)
                
                # Update status
                processed_global = min(overall_total, base_processed + i + 1)
                _parser_runs[parser_run_id]["processed"] = processed_global
                _parser_runs[parser_run_id]["total"] = overall_total
                _parser_runs[parser_run_id]["results"] = results
                await _sync_domain_parser_auto_progress(
                    run_id=run_id,
                    parser_run_id=parser_run_id,
                    processed=processed_global,
                    total=overall_total,
                    status="running",
                    last_domain=result.get("domain") or domain,
                )
                
                logger.info(f"Domain {domain} processed: INN={result.get('inn')}, Emails={result.get('emails')}")

                # If INN was not found AND worker is NOT paused, mark domain as requiring moderation.
                # This includes timeout/error cases — so the domain is not retried endlessly.
                # When paused mid-batch the domain should NOT be blacklisted so it can be retried.
                inn_found = bool(str(result.get("inn") or "").strip())
                was_skipped = str(result.get("reason") or "") in {"supplier_exists", "requires_moderation"}
                if not _worker_paused and not inn_found and not was_skipped:
                    error_str = str(result.get("error") or "").strip()
                    reason = error_str if error_str else "inn_not_found"
                    try:
                        await _mark_domain_requires_moderation(result.get("domain") or domain, reason)
                        result["dataStatus"] = "requires_moderation"
                    except Exception:
                        logger.warning("Failed to mark domain requires_moderation: %s", domain, exc_info=True)

                # Progressive enrichment: upsert supplier (and Checko) as soon as we have a result.
                # This allows cabinet/moderator tables to be updated gradually during the batch.
                try:
                    await _upsert_suppliers_from_domain_parser_results([result])
                except Exception as e:
                    logger.error(f"Progressive supplier upsert failed for domain {domain}: {e}", exc_info=True)

                # Sync run_domain status after enrichment
                if not was_skipped:
                    try:
                        source_urls = list(result.get("sourceUrls") or [])
                        extraction_log = result.get("extractionLog") or []
                        inn_url = None
                        email_url = None
                        for entry in extraction_log:
                            if isinstance(entry, dict):
                                if entry.get("inn_found") or entry.get("inn"):
                                    inn_url = inn_url or entry.get("url")
                                if entry.get("emails_found") or entry.get("emails"):
                                    email_url = email_url or entry.get("url")
                        if not inn_url and source_urls:
                            inn_url = source_urls[0] if inn_found else None
                        if not email_url and source_urls:
                            email_url = source_urls[0] if result.get("emails") else None

                        # AC-10: multiple INNs → requires_moderation
                        inns_raw = result.get("inns") or []
                        multiple_inns = len(inns_raw) > 2 if isinstance(inns_raw, list) else False

                        if multiple_inns:
                            rd_status = "requires_moderation"
                            rd_reason = "multiple_inn_found (>2)"
                        elif inn_found:
                            rd_status = str(result.get("dataStatus") or "supplier")
                            if rd_status == "complete":
                                rd_status = "supplier"
                            elif rd_status == "requires_moderation":
                                rd_status = "requires_moderation"
                            elif rd_status not in ("supplier", "reseller"):
                                rd_status = "supplier"
                            rd_reason = None
                        else:
                            rd_status = "requires_moderation"
                            rd_reason = str(result.get("error") or "inn_not_found")

                        # Determine supplier_id from result
                        rd_supplier_id = result.get("conflictSupplierId") or None
                        rd_checko_ok = str(result.get("dataStatus") or "") == "complete"

                        prev_snapshot = await _get_run_domain_attempted_urls(run_id=run_id, domain=result.get("domain") or domain)
                        prev_inn = None
                        prev_emails: list[str] = []
                        if isinstance(prev_snapshot, dict):
                            prev_inn = prev_snapshot.get("inn")
                            prev_emails = prev_snapshot.get("emails") or []
                        prev_has_data = bool(str(prev_inn or "").strip()) or bool(prev_emails)
                        now_inn = str(result.get("inn") or "").strip() or None
                        now_emails = result.get("emails") or []
                        now_has_data = bool(now_inn) or bool(now_emails)
                        learned = bool((not prev_has_data) and now_has_data)

                        snapshot_payload = {
                            "inn": now_inn,
                            "emails": now_emails,
                            "sourceUrls": source_urls,
                            "extractionLog": extraction_log,
                            "error": str(result.get("error") or "").strip() or None,
                            "learned": learned,
                            "previous": {"inn": prev_inn, "emails": prev_emails},
                            "strategyUsed": result.get("strategyUsed"),
                            "strategyTimeMs": result.get("strategyTimeMs"),
                        }

                        await _sync_run_domain_status(
                            run_id=run_id,
                            domain=result.get("domain") or domain,
                            status=rd_status,
                            reason=rd_reason,
                            attempted_urls=snapshot_payload,
                            inn_source_url=inn_url,
                            email_source_url=email_url,
                            supplier_id=rd_supplier_id,
                            checko_ok=rd_checko_ok,
                        )
                    except Exception:
                        logger.warning("Failed to sync run_domain after enrichment for %s", domain, exc_info=True)

                # --- PAUSE CHECK (after finishing a domain) ---
                if _worker_paused:
                    logger.info(
                        "Domain parser auto worker PAUSED after domain %s (%d/%d) — stopping batch",
                        domain, i + 1, len(domains),
                    )
                    paused_early = True
                    break
                
            except Exception as e:
                logger.error(f"Error processing domain {domain}: {e}")
                err_result = {
                    "domain": _normalize_domain(domain),
                    "inn": None,
                    "emails": [],
                    "sourceUrls": [],
                    "error": str(e)
                }
                results.append(err_result)
                processed_global = min(overall_total, base_processed + i + 1)
                _parser_runs[parser_run_id]["processed"] = processed_global
                _parser_runs[parser_run_id]["total"] = overall_total
                _parser_runs[parser_run_id]["results"] = results
                await _sync_domain_parser_auto_progress(
                    run_id=run_id,
                    parser_run_id=parser_run_id,
                    processed=processed_global,
                    total=overall_total,
                    status="running",
                    last_domain=domain,
                    error=str(e),
                )
                # Mark errored domain as requires_moderation so it's not retried endlessly
                if not _worker_paused:
                    try:
                        await _mark_domain_requires_moderation(_normalize_domain(domain), str(e)[:200])
                        err_result["dataStatus"] = "requires_moderation"
                    except Exception:
                        logger.warning("Failed to mark errored domain requires_moderation: %s", domain, exc_info=True)
                    # Sync run_domain for error case
                    try:
                        await _sync_run_domain_status(
                            run_id=run_id, domain=domain,
                            status="requires_moderation",
                            reason=str(e)[:200],
                        )
                    except Exception:
                        pass
        
        # Mark as completed
        _parser_runs[parser_run_id]["status"] = "completed"
        _parser_runs[parser_run_id]["finishedAt"] = datetime.now().isoformat()
        _parser_runs[parser_run_id]["processed"] = min(overall_total, base_processed + len(domains))
        _parser_runs[parser_run_id]["total"] = overall_total
        await _sync_domain_parser_auto_progress(
            run_id=run_id,
            parser_run_id=parser_run_id,
            processed=int(_parser_runs[parser_run_id]["processed"]),
            total=overall_total,
            status="completed",
        )
        
        # Save results to database
        await _save_parser_results_to_db(run_id, parser_run_id, results)

        # Enrich suppliers DB (moderator_suppliers) + Checko when INN is found
        try:
            await _upsert_suppliers_from_domain_parser_results(results)
        except Exception as e:
            logger.error(f"Failed to upsert suppliers from domain parser results: {e}", exc_info=True)
        
        logger.info(f"Domain parser batch completed: {parser_run_id}")
    except Exception as e:
        logger.error(f"Error in domain parser batch: {e}")
        _parser_runs[parser_run_id]["status"] = "failed"
        _parser_runs[parser_run_id]["error"] = str(e)
        await _sync_domain_parser_auto_progress(
            run_id=run_id,
            parser_run_id=parser_run_id,
            processed=int(_parser_runs.get(parser_run_id, {}).get("processed") or 0),
            total=int(_parser_runs.get(parser_run_id, {}).get("total") or len(domains)),
            status="failed",
            error=str(e),
        )


async def _run_domain_parser_for_domain(domain: str) -> Dict:
    """Run domain parser for a single domain using in-process browser (fast)."""
    logger.info(f"Running domain parser (in-process) for: {domain}")
    t0 = asyncio.get_event_loop().time()

    try:
        parser = await _get_inprocess_parser()
        result = await asyncio.wait_for(parser.parse_domain(domain), timeout=90.0)

        elapsed = asyncio.get_event_loop().time() - t0
        logger.info(f"Domain {domain} parsed in {elapsed:.1f}s — INN={result.get('inn')}, emails={result.get('emails')}")

        strategy_used = result.get("strategy_used") or result.get("strategy")
        strategy_time_ms = result.get("strategy_time_ms")

        return {
            "domain": result.get("domain", domain),
            "inn": result.get("inn"),
            "emails": result.get("emails", []),
            "sourceUrls": result.get("source_urls", []),
            "extractionLog": result.get("extraction_log", []),
            "error": result.get("error"),
            "strategyUsed": result.get("strategy_used"),
            "strategyTimeMs": result.get("strategy_time_ms"),
        }
    except asyncio.TimeoutError:
        logger.error(f"Domain parser timeout (90s) for {domain}")
        return {
            "domain": domain,
            "inn": None,
            "emails": [],
            "sourceUrls": [],
            "extractionLog": [{"url": f"https://{domain}", "error": "timeout (90s)"}],
            "error": "Parser timeout (90s)",
        }
    except Exception as e:
        logger.error(f"Error running domain parser for {domain}: {e}", exc_info=True)
        return {
            "domain": domain,
            "inn": None,
            "emails": [],
            "sourceUrls": [],
            "extractionLog": [{"url": f"https://{domain}", "error": str(e)[:200]}],
            "error": f"Parser error: {e}",
        }


async def _save_parser_results_to_db(run_id: str, parser_run_id: str, results: List[Dict]):
    """Save domain parser results to parsing run's process_log."""
    try:
        from app.adapters.db.session import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as session:
            try:
                res = await session.execute(
                    text("SELECT process_log FROM parsing_runs WHERE run_id = :run_id"),
                    {"run_id": run_id},
                )
                row = res.fetchone()
                if not row:
                    logger.error(f"Parsing run {run_id} not found when saving parser results")
                    return

                # Get existing process_log
                process_log = row[0]
                if isinstance(process_log, str):
                    try:
                        process_log = json.loads(process_log)
                    except json.JSONDecodeError:
                        process_log = {}
                elif not process_log:
                    process_log = {}
                
                # Ensure domain_parser structure exists
                if "domain_parser" not in process_log:
                    process_log["domain_parser"] = {"runs": {}}
                if "runs" not in process_log["domain_parser"]:
                    process_log["domain_parser"]["runs"] = {}
                
                # Save parser run results
                process_log["domain_parser"]["runs"][parser_run_id] = {
                    "status": "completed",
                    "started_at": datetime.now().isoformat(),
                    "finished_at": datetime.now().isoformat(),
                    "results": results
                }

                # Update parsing run (direct SQL to avoid SimpleNamespace)
                await session.execute(
                    text(
                        "UPDATE parsing_runs SET process_log = CAST(:process_log AS jsonb) WHERE run_id = :run_id"
                    ),
                    {
                        "process_log": json.dumps(process_log, ensure_ascii=False),
                        "run_id": run_id,
                    },
                )
                await session.commit()
                
                logger.info(f"Saved domain parser results for run {run_id}, parser_run_id {parser_run_id}")
            except Exception as e:
                logger.error(f"Error in save transaction: {e}")
                await session.rollback()
                raise
                
    except Exception as e:
        logger.error(f"Error saving domain parser results to DB: {e}")


async def _upsert_suppliers_from_domain_parser_results(results: List[Dict]) -> None:
    """Best-effort: create/update moderator_suppliers from extracted INN/emails and enrich via Checko."""
    from app.adapters.db.session import AsyncSessionLocal
    from app.adapters.db.repositories import ModeratorSupplierRepository
    from app.usecases import get_checko_data, update_moderator_supplier, create_moderator_supplier

    async with AsyncSessionLocal() as db:
        repo = ModeratorSupplierRepository(db)

        for r in results or []:
            try:
                domain_raw = str((r or {}).get("domain") or "").strip()
                domain = _normalize_domain(domain_raw)
                inn = str((r or {}).get("inn") or "").strip()
                emails = (r or {}).get("emails") or []
                if not isinstance(emails, list):
                    emails = []
                emails = [str(x).strip().lower() for x in emails if str(x).strip()]
                email = emails[0] if emails else None

                has_domain = bool(domain)
                has_inn = bool(inn)
                has_email = bool(email)

                if not has_domain:
                    continue

                # We only attempt DB upsert/enrichment when INN exists.
                # Without INN there is nothing to enrich via Checko and we avoid creating noisy records.
                if not has_inn:
                    r["dataStatus"] = "requires_moderation"
                    continue

                requires_moderation = not has_email

                # INN uniqueness:
                # if INN already exists on another supplier, bind this domain to that supplier
                # instead of skipping the record, so run UI can reflect supplier/checko status.
                existing_by_inn = await repo.get_by_inn(inn)
                linked_by_inn = False
                supplier = await repo.get_by_domain(domain)
                if existing_by_inn is not None and not bool(getattr(existing_by_inn, "allow_duplicate_inn", False)):
                    supplier = existing_by_inn
                    linked_by_inn = True
                    r["conflictInn"] = True
                    r["conflictSupplierId"] = int(existing_by_inn.id)
                    r["supplierLinkedByInn"] = True

                    # Ensure the discovered domain/email become attached to the existing supplier.
                    try:
                        await repo.add_domain(int(supplier.id), domain, is_primary=False)
                        for idx, em in enumerate(emails):
                            await repo.add_email(int(supplier.id), em, is_primary=bool(idx == 0))
                    except Exception:
                        pass

                    # Keep primary contacts fresh if missing on supplier card.
                    await update_moderator_supplier.execute(
                        db=db,
                        supplier_id=int(supplier.id),
                        supplier_data={
                            "domain": getattr(supplier, "domain", None) or domain,
                            "email": getattr(supplier, "email", None) or email,
                        },
                    )

                    # Checko block below is still executed for the resolved supplier.

                if supplier is None:
                    # Minimal creation (name is required)
                    supplier_data = {
                        "name": domain,
                        "domain": domain,
                        "type": "supplier" if not requires_moderation else "candidate",
                    }
                    
                    if inn:
                        supplier_data["inn"] = inn
                    if email:
                        supplier_data["email"] = email
                        
                    # Set status based on data completeness
                    if requires_moderation:
                        supplier_data["data_status"] = "needs_checko"
                    else:
                        supplier_data["data_status"] = "needs_checko"
                    
                    supplier = await create_moderator_supplier.execute(
                        db=db,
                        supplier_data=supplier_data,
                    )
                    r["supplierCreated"] = True
                elif not linked_by_inn:
                    # Update basic extracted contacts (only if available)
                    update_data = {"domain": domain}
                    if inn:
                        update_data["inn"] = inn
                    if email:
                        update_data["email"] = email

                    # Enforce project rule: type=supplier only when INN and Email exist
                    update_data["type"] = "supplier" if not requires_moderation else "candidate"
                    
                    # Set status based on data completeness
                    if requires_moderation:
                        update_data["data_status"] = "needs_checko"
                    elif inn:
                        update_data["data_status"] = "needs_checko"
                    
                    await update_moderator_supplier.execute(
                        db=db,
                        supplier_id=int(supplier.id),
                        supplier_data=update_data,
                    )
                    r["supplierUpdated"] = True

                # Persist domains/emails list
                try:
                    await repo.add_domain(int(supplier.id), domain, is_primary=True)
                    for idx, em in enumerate(emails):
                        await repo.add_email(int(supplier.id), em, is_primary=bool(idx == 0))
                except Exception:
                    pass

                # Always fetch Checko data when INN exists (even without email)
                if inn:
                    try:
                        checko = await get_checko_data.execute(db=db, inn=inn, force_refresh=False)
                        # Map frontend keys into supplier update fields (usecase normalizes camelCase)
                        await update_moderator_supplier.execute(
                            db=db,
                            supplier_id=int(supplier.id),
                            supplier_data={
                                "name": checko.get("name") or domain,
                                "ogrn": checko.get("ogrn"),
                                "kpp": checko.get("kpp"),
                                "okpo": checko.get("okpo"),
                                "companyStatus": checko.get("companyStatus"),
                                "registrationDate": checko.get("registrationDate"),
                                "legalAddress": checko.get("legalAddress"),
                                "phone": checko.get("phone"),
                                "website": checko.get("website"),
                                "vk": checko.get("vk"),
                                "telegram": checko.get("telegram"),
                                "authorizedCapital": checko.get("authorizedCapital"),
                                "revenue": checko.get("revenue"),
                                "profit": checko.get("profit"),
                                "financeYear": checko.get("financeYear"),
                                "legalCasesCount": checko.get("legalCasesCount"),
                                "legalCasesSum": checko.get("legalCasesSum"),
                                "legalCasesAsPlaintiff": checko.get("legalCasesAsPlaintiff"),
                                "legalCasesAsDefendant": checko.get("legalCasesAsDefendant"),
                                "checkoData": checko.get("checkoData"),
                                # 'complete' only when full required contacts exist
                                "data_status": "complete" if email else "requires_moderation",
                                "type": "supplier" if email else "candidate",
                            },
                        )
                        r["dataStatus"] = "complete" if email else "requires_moderation"
                    except Exception as e:
                        logger.warning(f"Checko enrich failed for domain={domain}, inn={inn}: {e}")
                        try:
                            await update_moderator_supplier.execute(
                                db=db,
                                supplier_id=int(supplier.id),
                                supplier_data={
                                    "data_status": "needs_checko",
                                },
                            )
                            r["dataStatus"] = "needs_checko"
                        except Exception:
                            pass
                elif not inn:
                    # No INN found — requires moderation
                    try:
                        await update_moderator_supplier.execute(
                            db=db,
                            supplier_id=int(supplier.id),
                            supplier_data={
                                "type": "candidate",
                                "data_status": "requires_moderation",
                            },
                        )
                        r["dataStatus"] = "requires_moderation"
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Supplier upsert failed for domain parser result {r}: {e}")

        await db.commit()
