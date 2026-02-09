"""Router for 'Текущая задача' block on /moderator dashboard.

Endpoints:
  GET  /moderator/current-task                              — active task FIFO
  POST /moderator/run-domains/{id}/manual-resolve           — atomic moderation
  POST /moderator/current-task/{run_id}/start-domain-parser — launch pending domains
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.adapters.db.session import get_db, AsyncSessionLocal
from app.transport.routers.auth import get_current_user
from app.utils.authz import require_moderator
from app.utils.domain import normalize_domain_root

logger = logging.getLogger(__name__)

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────────────────

def _norm(domain: str) -> str:
    """Normalize to root domain for consistent keys in run_domains."""
    return normalize_domain_root(domain)


def _get_processing_domain_from_memory(run_id: str) -> Optional[str]:
    """Read the currently-processing domain from the in-memory _parser_runs dict."""
    try:
        from app.transport.routers.domain_parser import _parser_runs
        for _pid, state in _parser_runs.items():
            if str(state.get("runId") or "") == run_id and state.get("status") == "running":
                cd = state.get("currentDomain")
                if cd:
                    return str(cd)
    except Exception:
        pass
    return None


def _is_parser_active_for_run(run_id: str) -> bool:
    """Check if the domain parser worker is actively processing this run."""
    try:
        from app.transport.routers.domain_parser import _parser_runs
        for _pid, state in _parser_runs.items():
            if str(state.get("runId") or "") == run_id and state.get("status") == "running":
                return True
    except Exception:
        pass
    return False


# ── Pydantic DTOs ────────────────────────────────────────────────────────────

class RunDomainDTO(BaseModel):
    id: int
    run_id: str
    domain: str
    status: str
    reason: Optional[str] = None
    attempted_urls: list = Field(default_factory=list)
    inn_source_url: Optional[str] = None
    email_source_url: Optional[str] = None
    supplier_id: Optional[int] = None
    checko_ok: bool = False
    global_requires_moderation: bool = False
    is_blacklisted: bool = False


class RunSummaryDTO(BaseModel):
    from_run_supplier: int = 0
    from_run_reseller: int = 0
    from_run_requires_moderation: int = 0
    from_run_with_checko: int = 0
    inherited: int = 0
    inherited_with_checko: int = 0
    total_passed: int = 0
    total_shown_to_user: int = 0
    pending_count: int = 0
    processing_count: int = 0


class CurrentRunDTO(BaseModel):
    run_id: str
    status: str
    keyword: Optional[str] = None
    created_at: Optional[str] = None
    domains: list[RunDomainDTO] = Field(default_factory=list)
    summary: RunSummaryDTO = Field(default_factory=RunSummaryDTO)
    processing_domain: Optional[str] = None
    parser_active: bool = False


class CurrentTaskDTO(BaseModel):
    task_id: Optional[int] = None
    task_title: Optional[str] = None
    task_created_at: Optional[str] = None
    request_id: Optional[int] = None
    queue_count: int = 0
    current_run: Optional[CurrentRunDTO] = None


class ManualResolveRequest(BaseModel):
    inn: str
    email: str
    inn_source_url: str
    email_source_url: str
    supplier_type: str = "supplier"


# ── GET /moderator/current-task ──────────────────────────────────────────────

@router.get("/current-task", response_model=CurrentTaskDTO)
async def get_current_task(
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return the active moderator task (FIFO) with 1 current run.

    Spec rules:
    - Show the oldest task that has an UNFINISHED run (pending/processing domains).
    - Current run = running run, or oldest not-completed run.
    - Domains shown as circles for that single run.
    - If all runs of a task are finished → task is done, skip it.
    """
    require_moderator(current_user)

    # 0. Eagerly populate run_domains for active tasks that don't have them yet
    try:
        unpop_res = await db.execute(
            text(
                "SELECT pr.run_id FROM parsing_runs pr "
                "JOIN moderator_tasks mt ON mt.request_id = pr.request_id "
                "WHERE mt.status NOT IN ('done','cancelled') "
                "AND pr.status = 'completed' "
                "AND EXISTS (SELECT 1 FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id) "
                "AND NOT EXISTS (SELECT 1 FROM run_domains rd WHERE rd.run_id = pr.run_id) "
                "ORDER BY pr.created_at DESC LIMIT 10"
            )
        )
        for row in (unpop_res.fetchall() or []):
            try:
                await _ensure_run_domains_populated(db, str(row[0]))
            except Exception:
                pass
    except Exception:
        logger.warning("Failed to eagerly populate run_domains", exc_info=True)

    # 1. Find active task: oldest task with a run that has pending/processing domains
    #    We try multiple strategies in order of specificity.
    task_row = None
    for query in [
        # (a) task with a running parsing_run
        ("SELECT mt.id, mt.request_id, mt.title, mt.created_at "
         "FROM moderator_tasks mt "
         "WHERE mt.status NOT IN ('done','cancelled') "
         "AND EXISTS (SELECT 1 FROM parsing_runs pr WHERE pr.request_id = mt.request_id "
         "  AND pr.status = 'running') "
         "ORDER BY mt.created_at ASC LIMIT 1"),
        # (b) task with a not-yet-completed run
        ("SELECT mt.id, mt.request_id, mt.title, mt.created_at "
         "FROM moderator_tasks mt "
         "WHERE mt.status NOT IN ('done','cancelled') "
         "AND EXISTS (SELECT 1 FROM parsing_runs pr WHERE pr.request_id = mt.request_id "
         "  AND pr.status NOT IN ('completed','failed')) "
         "ORDER BY mt.created_at ASC LIMIT 1"),
        # (c) task with pending/processing run_domains (run may be marked completed
        #     but still has unprocessed domains)
        ("SELECT mt.id, mt.request_id, mt.title, mt.created_at "
         "FROM moderator_tasks mt "
         "WHERE mt.status NOT IN ('done','cancelled') "
         "AND EXISTS (SELECT 1 FROM parsing_runs pr WHERE pr.request_id = mt.request_id "
         "  AND EXISTS (SELECT 1 FROM run_domains rd WHERE rd.run_id = pr.run_id "
         "    AND (rd.status IN ('pending','processing') OR rd.status IS NULL OR rd.status = ''))) "
         "ORDER BY mt.created_at ASC LIMIT 1"),
    ]:
        if task_row:
            break
        try:
            res = await db.execute(text(query))
            task_row = res.fetchone()
        except Exception:
            logger.warning("Failed to query moderator_tasks", exc_info=True)

    if not task_row:
        return CurrentTaskDTO()

    task_id = int(task_row[0])
    request_id = int(task_row[1])
    task_title = str(task_row[2] or "")
    task_created_at = task_row[3].isoformat() if task_row[3] else None

    # 2. Queue count: other tasks with unfinished runs
    queue_count = 0
    try:
        qres = await db.execute(
            text(
                "SELECT COUNT(*) FROM moderator_tasks mt "
                "WHERE mt.id != :tid AND mt.status NOT IN ('done','cancelled') "
                "AND EXISTS (SELECT 1 FROM parsing_runs pr WHERE pr.request_id = mt.request_id "
                "  AND pr.status NOT IN ('completed','failed'))"
            ),
            {"tid": task_id},
        )
        queue_count = int(qres.scalar() or 0)
    except Exception:
        pass

    # 3. Find current run: running first, then oldest not-completed
    run_row = None
    try:
        # Prefer a run that actually has pending/processing domains (spec requirement)
        res = await db.execute(
            text(
                "SELECT pr.run_id, pr.status, pr.created_at, "
                "COALESCE(preq.title, preq.raw_keys_json, '') AS keyword "
                "FROM parsing_runs pr "
                "LEFT JOIN parsing_requests preq ON preq.id = pr.request_id "
                "WHERE pr.request_id = :rid "
                "AND EXISTS (SELECT 1 FROM run_domains rd WHERE rd.run_id = pr.run_id "
                "  AND (rd.status IN ('pending','processing') OR rd.status IS NULL OR rd.status = '')) "
                "ORDER BY "
                "  CASE WHEN pr.status='running' THEN 0 "
                "       WHEN pr.status IN ('starting','queued') THEN 1 "
                "       ELSE 2 END, "
                "  pr.created_at ASC "
                "LIMIT 1"
            ),
            {"rid": request_id},
        )
        run_row = res.fetchone()

        if not run_row:
            # Fallback: pick a run by status ordering (used when run_domains are not yet populated)
            res = await db.execute(
                text(
                    "SELECT pr.run_id, pr.status, pr.created_at, "
                    "COALESCE(preq.title, preq.raw_keys_json, '') AS keyword "
                    "FROM parsing_runs pr "
                    "LEFT JOIN parsing_requests preq ON preq.id = pr.request_id "
                    "WHERE pr.request_id = :rid "
                    "ORDER BY "
                    "  CASE WHEN pr.status='running' THEN 0 "
                    "       WHEN pr.status IN ('starting','queued') THEN 1 "
                    "       ELSE 2 END, "
                    "  pr.created_at ASC "
                    "LIMIT 1"
                ),
                {"rid": request_id},
            )
            run_row = res.fetchone()
    except Exception:
        logger.warning("Failed to find current run", exc_info=True)

    if not run_row:
        return CurrentTaskDTO(
            task_id=task_id, task_title=task_title,
            task_created_at=task_created_at, request_id=request_id,
            queue_count=queue_count,
        )

    run_id = str(run_row[0])
    run_status = str(run_row[1])
    run_created_at = run_row[2].isoformat() if run_row[2] else None
    keyword = str(run_row[3] or "")

    # 4. Ensure run_domains populated
    try:
        await _ensure_run_domains_populated(db, run_id)
    except Exception:
        logger.warning("_ensure_run_domains_populated failed for %s", run_id, exc_info=True)

    # Sync processing domain from in-memory state
    processing_domain = _get_processing_domain_from_memory(run_id)
    if processing_domain:
        norm_pd = _norm(processing_domain)
        if norm_pd:
            try:
                await db.execute(
                    text(
                        "UPDATE run_domains SET status='processing', updated_at=NOW() "
                        "WHERE run_id=:rid AND domain=:dom AND status='pending'"
                    ),
                    {"rid": run_id, "dom": norm_pd},
                )
                await db.commit()
            except Exception:
                pass

    # 5. Fetch run_domains for this run
    domains_list: list[RunDomainDTO] = []
    try:
        dres = await db.execute(
            text(
                "SELECT rd.id, rd.run_id, rd.domain, rd.status, rd.reason, "
                "rd.attempted_urls, rd.inn_source_url, rd.email_source_url, "
                "rd.supplier_id, rd.checko_ok, rd.global_requires_moderation, "
                "EXISTS(SELECT 1 FROM blacklist bl WHERE lower(bl.domain)=lower(rd.domain)) AS is_bl "
                "FROM run_domains rd "
                "WHERE rd.run_id = :run_id "
                "ORDER BY rd.id ASC"
            ),
            {"run_id": run_id},
        )
        for row in dres.fetchall():
            is_bl = bool(row[11])
            attempted = row[5] if isinstance(row[5], list) else []
            domains_list.append(RunDomainDTO(
                id=int(row[0]), run_id=str(row[1]), domain=str(row[2]),
                status=str(row[3]), reason=row[4], attempted_urls=attempted,
                inn_source_url=row[6], email_source_url=row[7],
                supplier_id=int(row[8]) if row[8] else None,
                checko_ok=bool(row[9]), global_requires_moderation=bool(row[10]),
                is_blacklisted=is_bl,
            ))
    except Exception:
        logger.warning("Failed to get run_domains for run %s", run_id, exc_info=True)

    # Filter out blacklisted
    visible = [d for d in domains_list if not d.is_blacklisted]

    # 6. Summary per spec
    s_sup = sum(1 for d in visible if d.status == "supplier" and not d.global_requires_moderation)
    s_res = sum(1 for d in visible if d.status == "reseller" and not d.global_requires_moderation)
    s_rm = sum(1 for d in visible if d.status == "requires_moderation")
    s_chk = sum(1 for d in visible if d.status in ("supplier", "reseller") and d.checko_ok and not d.global_requires_moderation)
    inherited = sum(1 for d in visible if d.status in ("supplier", "reseller") and d.global_requires_moderation)
    inherited_chk = sum(1 for d in visible if d.status in ("supplier", "reseller") and d.global_requires_moderation and d.checko_ok)
    pending_cnt = sum(1 for d in visible if d.status == "pending")
    processing_cnt = sum(1 for d in visible if d.status == "processing")
    total_passed = s_sup + s_res + inherited
    total_shown = s_chk + inherited_chk

    parser_active = _is_parser_active_for_run(run_id)

    summary = RunSummaryDTO(
        from_run_supplier=s_sup, from_run_reseller=s_res,
        from_run_requires_moderation=s_rm, from_run_with_checko=s_chk,
        inherited=inherited, inherited_with_checko=inherited_chk,
        total_passed=total_passed, total_shown_to_user=total_shown,
        pending_count=pending_cnt, processing_count=processing_cnt,
    )

    current_run = CurrentRunDTO(
        run_id=run_id, status=run_status, keyword=keyword,
        created_at=run_created_at, domains=visible, summary=summary,
        processing_domain=processing_domain,
        parser_active=parser_active,
    )

    return CurrentTaskDTO(
        task_id=task_id, task_title=task_title,
        task_created_at=task_created_at, request_id=request_id,
        queue_count=queue_count, current_run=current_run,
    )


# ── _ensure_run_domains_populated ────────────────────────────────────────────

async def _ensure_run_domains_populated(db, run_id: str) -> None:
    """Populate run_domains from domains_queue using normalize_domain_root.

    Key fix: domains are normalized to root domain before INSERT so that
    _sync_run_domain_status (which also normalizes) matches the same key.
    Already-global supplier/reseller → status=supplier/reseller (inherited).
    Already-global requires_moderation → status=requires_moderation + global flag.
    """
    try:
        cnt_res = await db.execute(
            text("SELECT COUNT(*) FROM run_domains WHERE run_id = :rid"),
            {"rid": run_id},
        )
        cnt = int(cnt_res.scalar() or 0)

        if cnt > 0:
            # Check if existing entries need re-normalization:
            # - contain :// or www. prefix
            # - are subdomains (3+ dot-separated parts like spb.metallprofil.ru)
            bad_res = await db.execute(
                text(
                    "SELECT domain FROM run_domains "
                    "WHERE run_id = :rid "
                    "LIMIT 200"
                ),
                {"rid": run_id},
            )
            needs_renorm = False
            for row in (bad_res.fetchall() or []):
                d = str(row[0] or "")
                normed = _norm(d)
                if normed != d:
                    needs_renorm = True
                    break
            if not needs_renorm:
                return
            # Old entries with wrong normalization — delete and re-populate
            logger.info("Re-normalizing run_domains for run %s (found un-normalized domains)", run_id)
            await db.execute(
                text("DELETE FROM run_domains WHERE run_id = :rid"),
                {"rid": run_id},
            )
            await db.commit()

        # Fetch raw domains from queue
        dq_res = await db.execute(
            text("SELECT DISTINCT domain FROM domains_queue WHERE parsing_run_id = :rid"),
            {"rid": run_id},
        )
        raw_domains = [str(r[0]).strip() for r in (dq_res.fetchall() or []) if r and r[0]]

        if not raw_domains:
            return

        # Normalize and deduplicate
        seen: set[str] = set()
        unique_domains: list[str] = []
        for rd in raw_domains:
            nd = _norm(rd)
            if nd and nd not in seen:
                seen.add(nd)
                unique_domains.append(nd)

        # For each normalized domain, determine initial status
        for dom in unique_domains:
            # Check global supplier
            sup_res = await db.execute(
                text(
                    "SELECT ms.id, ms.type, ms.data_status FROM moderator_suppliers ms "
                    "LEFT JOIN supplier_domains sd ON sd.supplier_id = ms.id "
                    "WHERE replace(lower(COALESCE(sd.domain, ms.domain, '')), 'www.', '') = :d "
                    "   OR replace(lower(COALESCE(sd.domain, ms.domain, '')), 'www.', '') "
                    "      LIKE '%' || :d "
                    "LIMIT 1"
                ),
                {"d": dom},
            )
            sup_row = sup_res.fetchone()

            if sup_row and str(sup_row[1] or "") in ("supplier", "reseller"):
                # Already a global supplier/reseller → inherited
                sid = int(sup_row[0])
                stype = str(sup_row[1])
                ds = str(sup_row[2] or "")
                await db.execute(
                    text(
                        "INSERT INTO run_domains (run_id, domain, status, supplier_id, "
                        "  checko_ok, global_requires_moderation) "
                        "VALUES (:rid, :dom, :st, :sid, :chk, FALSE) "
                        "ON CONFLICT (run_id, domain) DO NOTHING"
                    ),
                    {"rid": run_id, "dom": dom, "st": stype, "sid": sid, "chk": ds == "complete"},
                )
                continue

            # Check global requires_moderation
            mod_res = await db.execute(
                text(
                    "SELECT reason FROM domain_moderation "
                    "WHERE replace(lower(domain), 'www.', '') = :d "
                    "LIMIT 1"
                ),
                {"d": dom},
            )
            mod_row = mod_res.fetchone()
            if mod_row:
                await db.execute(
                    text(
                        "INSERT INTO run_domains (run_id, domain, status, reason, "
                        "  global_requires_moderation) "
                        "VALUES (:rid, :dom, 'requires_moderation', :reason, TRUE) "
                        "ON CONFLICT (run_id, domain) DO NOTHING"
                    ),
                    {"rid": run_id, "dom": dom, "reason": mod_row[0]},
                )
                continue

            # Truly pending
            await db.execute(
                text(
                    "INSERT INTO run_domains (run_id, domain, status) "
                    "VALUES (:rid, :dom, 'pending') "
                    "ON CONFLICT (run_id, domain) DO NOTHING"
                ),
                {"rid": run_id, "dom": dom},
            )

        await db.commit()
    except Exception:
        logger.warning("Failed to populate run_domains for run %s", run_id, exc_info=True)
        try:
            await db.rollback()
        except Exception:
            pass


# ── GET /moderator/unprocessed-runs ──────────────────────────────────────────

@router.get("/unprocessed-runs")
async def get_unprocessed_runs(
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return parsing runs that have domains without final status (pending/processing).

    Used by the dashboard to show which runs still need domain parser processing.
    Returns runs ordered by creation date, with counts of pending/total domains.
    """
    require_moderator(current_user)

    runs = []
    try:
        res = await db.execute(
            text(
                "SELECT pr.run_id, pr.status, pr.created_at, "
                "COALESCE(preq.title, preq.raw_keys_json, '') AS keyword, "
                "COUNT(rd.id) AS total_domains, "
                "SUM(CASE WHEN rd.status = 'pending' THEN 1 ELSE 0 END) AS pending_count, "
                "SUM(CASE WHEN rd.status = 'processing' THEN 1 ELSE 0 END) AS processing_count, "
                "SUM(CASE WHEN rd.status = 'supplier' THEN 1 ELSE 0 END) AS supplier_count, "
                "SUM(CASE WHEN rd.status = 'reseller' THEN 1 ELSE 0 END) AS reseller_count, "
                "SUM(CASE WHEN rd.status = 'requires_moderation' THEN 1 ELSE 0 END) AS moderation_count "
                "FROM parsing_runs pr "
                "LEFT JOIN parsing_requests preq ON preq.id = pr.request_id "
                "INNER JOIN run_domains rd ON rd.run_id = pr.run_id "
                "GROUP BY pr.run_id, pr.status, pr.created_at, preq.title, preq.raw_keys_json "
                "HAVING SUM(CASE WHEN rd.status IN ('pending','processing') THEN 1 ELSE 0 END) > 0 "
                "ORDER BY pr.created_at ASC "
                "LIMIT 20"
            )
        )
        for row in res.fetchall():
            parser_active = _is_parser_active_for_run(str(row[0]))
            runs.append({
                "run_id": str(row[0]),
                "status": str(row[1]),
                "created_at": row[2].isoformat() if row[2] else None,
                "keyword": str(row[3] or ""),
                "total_domains": int(row[4] or 0),
                "pending_count": int(row[5] or 0),
                "processing_count": int(row[6] or 0),
                "supplier_count": int(row[7] or 0),
                "reseller_count": int(row[8] or 0),
                "moderation_count": int(row[9] or 0),
                "parser_active": parser_active,
            })
    except Exception:
        logger.warning("Failed to get unprocessed runs", exc_info=True)

    return {"runs": runs, "total": len(runs)}


@router.post("/current-task/resume-all")
async def resume_all_processing(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Resume processing: find the first run with pending domains and start parser.

    After the parser finishes one run, the auto-worker will pick the next one.
    """
    require_moderator(current_user)

    # Check if parser is already running for any run
    try:
        from app.transport.routers.domain_parser import _parser_runs
        for _pid, state in _parser_runs.items():
            if state.get("status") == "running":
                return {
                    "success": True,
                    "message": "Parser already running",
                    "run_id": str(state.get("runId", "")),
                    "parser_run_id": str(state.get("parserRunId", "")),
                    "already_running": True,
                }
    except Exception:
        pass

    # Find first run with pending domains
    first_run_id = None
    pending_count = 0
    async with AsyncSessionLocal() as db:
        try:
            res = await db.execute(
                text(
                    "SELECT rd.run_id, COUNT(*) AS cnt "
                    "FROM run_domains rd "
                    "WHERE rd.status = 'pending' "
                    "GROUP BY rd.run_id "
                    "ORDER BY MIN(rd.id) ASC "
                    "LIMIT 1"
                )
            )
            row = res.fetchone()
            if row:
                first_run_id = str(row[0])
                pending_count = int(row[1])
        except Exception:
            logger.warning("Failed to find first pending run", exc_info=True)

    if not first_run_id:
        return {"success": False, "message": "No pending domains found", "run_id": None}

    # Delegate to start_domain_parser_for_run
    # We need to call it programmatically
    import uuid
    from datetime import datetime
    from app.transport.routers import domain_parser

    pending_domains: list[str] = []
    async with AsyncSessionLocal() as db:
        try:
            res = await db.execute(
                text(
                    "SELECT domain FROM run_domains "
                    "WHERE run_id = :rid AND status = 'pending' "
                    "ORDER BY id ASC"
                ),
                {"rid": first_run_id},
            )
            pending_domains = [str(r[0]) for r in (res.fetchall() or []) if r and r[0]]
        except Exception:
            pass

    if not pending_domains:
        return {"success": False, "message": "No pending domains found", "run_id": first_run_id}

    parser_run_id = f"resume_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    domain_parser._parser_runs[parser_run_id] = {
        "runId": first_run_id,
        "parserRunId": parser_run_id,
        "keyword": "",
        "status": "running",
        "processed": 0,
        "total": len(pending_domains),
        "baseProcessed": 0,
        "overallTotal": len(pending_domains),
        "currentDomain": None,
        "currentSourceUrls": [],
        "results": [],
        "startedAt": datetime.utcnow().isoformat(),
        "auto": False,
        "resume_mode": True,
    }

    background_tasks.add_task(
        domain_parser._process_domain_parser_batch,
        parser_run_id, first_run_id, pending_domains,
    )

    return {
        "success": True,
        "message": f"Started processing {len(pending_domains)} domains",
        "run_id": first_run_id,
        "parser_run_id": parser_run_id,
        "pending_count": len(pending_domains),
        "already_running": False,
    }


# ── POST start-domain-parser ─────────────────────────────────────────────────

@router.post("/current-task/{run_id}/start-domain-parser")
async def start_domain_parser_for_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Launch domain parser batch for pending domains of a specific run."""
    require_moderator(current_user)

    # Check parser not already active for this run
    if _is_parser_active_for_run(run_id):
        raise HTTPException(status_code=409, detail="Parser already active for this run")

    # Collect pending domains from run_domains
    pending_domains: list[str] = []
    async with AsyncSessionLocal() as db:
        try:
            res = await db.execute(
                text(
                    "SELECT domain FROM run_domains "
                    "WHERE run_id = :rid AND status = 'pending' "
                    "ORDER BY id ASC"
                ),
                {"rid": run_id},
            )
            pending_domains = [str(r[0]) for r in (res.fetchall() or []) if r and r[0]]
        except Exception:
            logger.warning("Failed to get pending domains for run %s", run_id, exc_info=True)

    if not pending_domains:
        raise HTTPException(status_code=404, detail="No pending domains for this run")

    # Launch batch via domain_parser
    import uuid
    from datetime import datetime
    from app.transport.routers import domain_parser

    parser_run_id = f"manual_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    domain_parser._parser_runs[parser_run_id] = {
        "runId": run_id,
        "parserRunId": parser_run_id,
        "keyword": "",
        "status": "running",
        "processed": 0,
        "total": len(pending_domains),
        "baseProcessed": 0,
        "overallTotal": len(pending_domains),
        "currentDomain": None,
        "currentSourceUrls": [],
        "results": [],
        "startedAt": datetime.utcnow().isoformat(),
        "auto": False,
    }

    # Update process_log in DB
    try:
        async with AsyncSessionLocal() as db:
            pl_res = await db.execute(
                text("SELECT process_log FROM parsing_runs WHERE run_id = :rid"),
                {"rid": run_id},
            )
            pl_row = pl_res.fetchone()
            pl = pl_row[0] if pl_row else None
            if isinstance(pl, str):
                try:
                    pl = json.loads(pl)
                except Exception:
                    pl = {}
            if not isinstance(pl, dict):
                pl = {}
            pl["domain_parser_auto"] = {
                "status": "running",
                "parserRunId": parser_run_id,
                "mode": "manual_start",
                "pickedAt": datetime.utcnow().isoformat(),
                "total": len(pending_domains),
                "processed": 0,
            }
            await db.execute(
                text("UPDATE parsing_runs SET process_log = CAST(:pl AS jsonb) WHERE run_id = :rid"),
                {"pl": json.dumps(pl, ensure_ascii=False), "rid": run_id},
            )
            await db.commit()
    except Exception:
        logger.warning("Failed to update process_log for manual start", exc_info=True)

    background_tasks.add_task(
        domain_parser._process_domain_parser_batch,
        parser_run_id, run_id, pending_domains,
    )

    return {
        "success": True,
        "parser_run_id": parser_run_id,
        "pending_count": len(pending_domains),
        "run_id": run_id,
    }


# ── POST /moderator/run-domains/{id}/manual-resolve ──────────────────────────

@router.post("/run-domains/{run_domain_id}/manual-resolve")
async def manual_resolve_domain(
    run_domain_id: int,
    body: ManualResolveRequest,
    current_user: dict = Depends(get_current_user),
):
    """Atomic manual moderation: upsert supplier, update run_domain, try Checko."""
    require_moderator(current_user)

    async with AsyncSessionLocal() as db:
        try:
            # 1. Get run_domain record
            rd_res = await db.execute(
                text("SELECT id, run_id, domain, status FROM run_domains WHERE id = :id"),
                {"id": run_domain_id},
            )
            rd_row = rd_res.fetchone()
            if not rd_row:
                raise HTTPException(status_code=404, detail="Run domain not found")

            domain = str(rd_row[2])
            inn = body.inn.strip()
            email = body.email.strip().lower()
            inn_source_url = body.inn_source_url.strip()
            email_source_url = body.email_source_url.strip()
            supplier_type = body.supplier_type if body.supplier_type in ("supplier", "reseller") else "supplier"

            if not inn or not email:
                raise HTTPException(status_code=400, detail="INN and email are required")

            # 2. Upsert supplier
            from app.adapters.db.repositories import ModeratorSupplierRepository
            repo = ModeratorSupplierRepository(db)

            supplier = await repo.get_by_domain(domain)
            existing_by_inn = await repo.get_by_inn(inn)

            if existing_by_inn and not supplier:
                supplier = existing_by_inn

            supplier_id: int
            if supplier:
                supplier_id = int(supplier.id)
                await db.execute(
                    text(
                        "UPDATE moderator_suppliers SET "
                        "inn = :inn, email = :email, domain = :domain, "
                        "type = :stype, data_status = 'needs_checko', "
                        "updated_at = NOW() "
                        "WHERE id = :sid"
                    ),
                    {"inn": inn, "email": email, "domain": domain, "stype": supplier_type, "sid": supplier_id},
                )
            else:
                ins_res = await db.execute(
                    text(
                        "INSERT INTO moderator_suppliers (name, inn, email, domain, type, data_status) "
                        "VALUES (:name, :inn, :email, :domain, :stype, 'needs_checko') "
                        "RETURNING id"
                    ),
                    {"name": domain, "inn": inn, "email": email, "domain": domain, "stype": supplier_type},
                )
                supplier_id = int(ins_res.scalar())

            # Persist domain and email links
            try:
                await db.execute(
                    text(
                        "INSERT INTO supplier_domains (supplier_id, domain, is_primary) "
                        "VALUES (:sid, :dom, TRUE) "
                        "ON CONFLICT (supplier_id, domain) DO NOTHING"
                    ),
                    {"sid": supplier_id, "dom": domain},
                )
                await db.execute(
                    text(
                        "INSERT INTO supplier_emails (supplier_id, email, is_primary) "
                        "VALUES (:sid, :em, TRUE) "
                        "ON CONFLICT (supplier_id, email) DO NOTHING"
                    ),
                    {"sid": supplier_id, "em": email},
                )
            except Exception:
                pass

            # 3. Remove from domain_moderation (resolved)
            await db.execute(
                text("DELETE FROM domain_moderation WHERE domain = :dom"),
                {"dom": domain},
            )

            # 4. Try Checko
            checko_ok = False
            try:
                from app.usecases import get_checko_data, update_moderator_supplier
                checko = await get_checko_data.execute(db=db, inn=inn, force_refresh=False)
                if checko and isinstance(checko, dict):
                    await update_moderator_supplier.execute(
                        db=db,
                        supplier_id=supplier_id,
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
                            "data_status": "complete",
                            "type": supplier_type,
                        },
                    )
                    checko_ok = True
            except Exception as e:
                logger.warning("Checko fetch failed for INN %s: %s", inn, e)

            # 5. Update run_domain atomically
            await db.execute(
                text(
                    "UPDATE run_domains SET "
                    "status = :status, reason = NULL, "
                    "inn_source_url = :inn_url, email_source_url = :email_url, "
                    "supplier_id = :sid, checko_ok = :checko_ok, "
                    "global_requires_moderation = FALSE, "
                    "updated_at = NOW() "
                    "WHERE id = :id"
                ),
                {
                    "status": supplier_type,
                    "inn_url": inn_source_url,
                    "email_url": email_source_url,
                    "sid": supplier_id,
                    "checko_ok": checko_ok,
                    "id": run_domain_id,
                },
            )

            await db.commit()

            return {
                "success": True,
                "run_domain_id": run_domain_id,
                "supplier_id": supplier_id,
                "status": supplier_type,
                "checko_ok": checko_ok,
            }

        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error("Manual resolve failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# ── GET run_domains for a specific run ───────────────────────────────────────

@router.get("/run-domains/{run_id}")
async def get_run_domains(
    run_id: str,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return all run_domains rows for a given parsing run.

    Used by /parsing-runs/[runId] page to display reason, attempted_urls,
    inn_source_url, email_source_url per domain.
    """
    require_moderator(current_user)

    rows = await db.execute(
        text(
            "SELECT rd.id, rd.run_id, rd.domain, rd.status, rd.reason, "
            "       rd.attempted_urls, rd.inn_source_url, rd.email_source_url, "
            "       rd.supplier_id, rd.checko_ok, rd.global_requires_moderation "
            "FROM run_domains rd "
            "WHERE rd.run_id = :run_id "
            "ORDER BY rd.domain ASC"
        ),
        {"run_id": run_id},
    )
    result = []
    for r in rows.fetchall():
        attempted = r[5]
        if isinstance(attempted, str):
            try:
                attempted = json.loads(attempted)
            except Exception:
                attempted = []
        result.append({
            "id": r[0],
            "run_id": str(r[1]),
            "domain": r[2],
            "status": r[3] or "pending",
            "reason": r[4],
            "attempted_urls": attempted or [],
            "inn_source_url": r[6],
            "email_source_url": r[7],
            "supplier_id": r[8],
            "checko_ok": bool(r[9]),
            "global_requires_moderation": bool(r[10]),
        })

    return {"run_id": run_id, "domains": result, "total": len(result)}
