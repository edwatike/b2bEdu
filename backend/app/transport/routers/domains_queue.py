"""Router for domains queue."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.adapters.db.session import get_db
from app.transport.schemas.domain import (
    DomainQueueEntryDTO,
    DomainsQueueResponseDTO,
    PendingDomainsResponseDTO,
    PendingDomainDTO,
)
from app.transport.routers.auth import can_access_moderator_zone, get_current_user
from app.config import settings
from app.usecases import (
    list_domains_queue,
    remove_from_domains_queue,
)

router = APIRouter()


class EnrichDomainRequest(BaseModel):
    domain: str


class EnrichDomainResponse(BaseModel):
    domain: str
    inn: str | None = None
    emails: list[str] = []
    status: str
    error: str | None = None


class ClearPendingDomainsRequest(BaseModel):
    domains: list[str] | None = None


def _require_moderator(current_user: dict):
    # Dev-only relaxation to allow local testing without strict email-based moderator checks
    if str(getattr(settings, "ENV", "")).lower() == "development":
        return
    role = str(current_user.get("role") or "")
    username = str(current_user.get("username") or "")
    if role in {"admin", "moderator"}:
        return
    if username == "admin":
        return
    if not can_access_moderator_zone(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _root_domain_sql(field: str) -> str:
    # Normalize to root domain:
    # 1) strip scheme, path, port
    # 2) remove www
    # 3) collapse subdomains to last 2 labels
    # Example: https://spb.pulscen.ru/path -> pulscen.ru
    cleaned = f"btrim(lower({field}))"
    cleaned = f"regexp_replace({cleaned}, '^https?://', '')"
    cleaned = f"regexp_replace({cleaned}, '/.*$', '')"
    cleaned = f"regexp_replace({cleaned}, ':[0-9]+$', '')"
    cleaned = f"regexp_replace({cleaned}, '^www\\.', '')"
    base = f"regexp_replace({cleaned}, '^.*?([^.]+\\.[^.]+)$', '\\1')"
    # Normalize regional suffixes (e.g., kraska-spb.ru -> kraska.ru)
    return f"regexp_replace({base}, '^(.*?)-(spb|ekb)\\.', '\\1.', 'i')"


@router.get("/queue", response_model=DomainsQueueResponseDTO)
async def list_domains_queue_endpoint(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    parsingRunId: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List domains queue entries with pagination."""
    import logging
    logger = logging.getLogger(__name__)

    _require_moderator(current_user)
    
    # Валидация и нормализация параметров
    if parsingRunId:
        parsingRunId = parsingRunId.strip()
        if not parsingRunId:
            parsingRunId = None
    
    if keyword:
        keyword = keyword.strip()
        if not keyword:
            keyword = None
    
    logger.info(f"list_domains_queue_endpoint called with parsingRunId={parsingRunId}, keyword={keyword}, status={status}")
    
    # DEBUG: Log the actual parameter value
    if parsingRunId:
        logger.info(f"DEBUG: parsingRunId value: '{parsingRunId}' (type: {type(parsingRunId)}, len: {len(parsingRunId)})")
    
    entries, total = await list_domains_queue.execute(
        db=db,
        limit=limit,
        offset=offset,
        status=status,
        keyword=keyword,
        parsing_run_id=parsingRunId  # Pass parsingRunId as parsing_run_id
    )
    
    logger.info(f"list_domains_queue_endpoint returning {len(entries)} entries, total={total}")
    
    # CRITICAL FIX: Use model_validate with from_attributes=True for SQLAlchemy models
    # This properly handles all fields including parsing_run_id
    try:
        dto_entries = [
            DomainQueueEntryDTO.model_validate(entry, from_attributes=True)
            for entry in entries
        ]
    except Exception as e:
        logger.error(f"Error converting entries to DTO: {e}", exc_info=True)
        # Fallback: convert to dict manually
        entries_dicts = []
        for entry in entries:
            entry_dict = {
                "domain": entry.domain,
                "keyword": entry.keyword,
                "url": entry.url,
                "parsing_run_id": entry.parsing_run_id,
                "status": entry.status,
                "created_at": entry.created_at
            }
            entries_dicts.append(entry_dict)
        dto_entries = [DomainQueueEntryDTO.model_validate(e) for e in entries_dicts]
    
    return DomainsQueueResponseDTO(
        entries=dto_entries,
        total=total,
        limit=limit,
        offset=offset
    )


@router.delete("/queue/{domain}", status_code=204)
async def remove_from_domains_queue_endpoint(
    domain: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove domain from queue."""
    _require_moderator(current_user)
    success = await remove_from_domains_queue.execute(db=db, domain=domain)
    if not success:
        raise HTTPException(status_code=404, detail="Domain not found in queue")
    
    await db.commit()


@router.get("/pending", response_model=PendingDomainsResponseDTO)
async def list_pending_domains_endpoint(
    limit: int = Query(default=50, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List unique pending domains (not in blacklist and not in suppliers)."""
    from sqlalchemy import text
    import re

    _require_moderator(current_user)

    search_term = (search or "").strip().lower()
    if search_term:
        # Normalize user input to a domain-like substring (strip scheme/path/port/www).
        search_term = re.sub(r"^https?://", "", search_term)
        search_term = search_term.split("/", 1)[0]
        search_term = re.sub(r":\d+$", "", search_term)
        search_term = re.sub(r"^www\\.", "", search_term)
        search_term = search_term.strip()
    if not search_term:
        search_term = ""

    root_domain_expr = _root_domain_sql("dq.domain")
    blacklist_expr = _root_domain_sql("b.domain")
    supplier_expr = _root_domain_sql("s.domain")
    supplier_domains_expr = _root_domain_sql("sd.domain")

    search_filter = ""
    params = {"limit": int(limit), "offset": int(offset)}
    if search_term:
        search_filter = " AND d ILIKE :search"
        params["search"] = f"%{search_term}%"

    base_cte = (
        "WITH normalized_domains AS ("
        f"  SELECT {root_domain_expr} AS d, "
        "         MAX(dq.created_at) AS last_seen_at, "
        "         COUNT(*) AS occurrences "
        "  FROM domains_queue dq "
        "  GROUP BY d "
        "), "
        "blacklisted AS ("
        f"  SELECT DISTINCT {blacklist_expr} AS d FROM blacklist b WHERE b.domain IS NOT NULL"
        "), "
        "supplier_domains_all AS ("
        f"  SELECT DISTINCT {supplier_expr} AS d FROM moderator_suppliers s WHERE s.domain IS NOT NULL "
        "  UNION "
        f"  SELECT DISTINCT {supplier_domains_expr} AS d FROM supplier_domains sd WHERE sd.domain IS NOT NULL"
        "), "
        "pending AS ("
        "  SELECT * FROM normalized_domains "
        "  WHERE d IS NOT NULL AND d <> '' "
        "    AND d NOT IN (SELECT d FROM blacklisted) "
        "    AND d NOT IN (SELECT d FROM supplier_domains_all)"
        f"{search_filter}"
        ") "
    )

    q = await db.execute(
        text(
            base_cte
            + "SELECT d, occurrences, last_seen_at "
            "FROM pending "
            "ORDER BY last_seen_at DESC NULLS LAST, d ASC "
            "LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    rows = q.fetchall() or []

    count_params = {"search": params["search"]} if search_term else None
    count_q = await db.execute(text(base_cte + "SELECT COUNT(*) FROM pending"), count_params)
    total = int(count_q.scalar() or 0)

    entries = [
        PendingDomainDTO(domain=str(r[0]), occurrences=int(r[1] or 0), last_seen_at=r[2])
        for r in rows
        if r and r[0]
    ]

    return PendingDomainsResponseDTO(entries=entries, total=total, limit=limit, offset=offset)


@router.post("/pending/enrich", response_model=EnrichDomainResponse)
async def enrich_pending_domain(
    payload: EnrichDomainRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Run domain parser for a single pending domain and upsert supplier/Checko data."""
    _require_moderator(current_user)
    domain = (payload.domain or "").strip()
    if not domain:
        raise HTTPException(status_code=422, detail="Domain is required")

    try:
        from app.transport.routers import domain_parser as domain_parser_router
        from app.utils.domain import normalize_domain_root

        result = await domain_parser_router._run_domain_parser_for_domain(domain)
        try:
            result["domain"] = normalize_domain_root(result.get("domain") or domain)
        except Exception:
            pass

        try:
            await domain_parser_router._upsert_suppliers_from_domain_parser_results([result])
        except Exception as e:
            return EnrichDomainResponse(
                domain=str(result.get("domain") or domain),
                inn=result.get("inn"),
                emails=list(result.get("emails") or []),
                status="failed",
                error=f"Supplier upsert failed: {e}",
            )

        return EnrichDomainResponse(
            domain=str(result.get("domain") or domain),
            inn=result.get("inn"),
            emails=list(result.get("emails") or []),
            status="completed",
            error=result.get("error"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Domain enrichment failed: {e}")


@router.post("/pending/clear")
async def clear_pending_domains(
    payload: ClearPendingDomainsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete pending domains from domains_queue (they can reappear on next parsing runs)."""
    from sqlalchemy import text
    import re

    _require_moderator(current_user)

    domains = payload.domains if payload and payload.domains else []
    normalized: list[str] = []
    for d in domains:
        if not d:
            continue
        s = str(d).strip().lower()
        if not s:
            continue
        s = re.sub(r"^https?://", "", s)
        s = s.split("/", 1)[0]
        s = re.sub(r":\d+$", "", s)
        s = re.sub(r"^www\.", "", s)
        if s:
            normalized.append(s)

    root_domain_expr = _root_domain_sql("dq.domain")
    blacklist_expr = _root_domain_sql("b.domain")
    supplier_expr = _root_domain_sql("s.domain")
    supplier_domains_expr = _root_domain_sql("sd.domain")

    filter_clause = ""
    params: dict[str, object] = {}
    if normalized:
        filter_clause = " AND d = ANY(:domains)"
        params["domains"] = normalized

    base_cte = (
        "WITH normalized_domains AS ("
        f"  SELECT {root_domain_expr} AS d "
        "  FROM domains_queue dq "
        "  GROUP BY d "
        "), "
        "blacklisted AS ("
        f"  SELECT DISTINCT {blacklist_expr} AS d FROM blacklist b WHERE b.domain IS NOT NULL"
        "), "
        "supplier_domains_all AS ("
        f"  SELECT DISTINCT {supplier_expr} AS d FROM moderator_suppliers s WHERE s.domain IS NOT NULL "
        "  UNION "
        f"  SELECT DISTINCT {supplier_domains_expr} AS d FROM supplier_domains sd WHERE sd.domain IS NOT NULL"
        "), "
        "pending AS ("
        "  SELECT * FROM normalized_domains "
        "  WHERE d IS NOT NULL AND d <> '' "
        "    AND d NOT IN (SELECT d FROM blacklisted) "
        "    AND d NOT IN (SELECT d FROM supplier_domains_all)"
        f"{filter_clause}"
        ") "
    )

    delete_q = await db.execute(
        text(
            base_cte
            + "DELETE FROM domains_queue dq "
            f"WHERE {_root_domain_sql('dq.domain')} IN (SELECT d FROM pending) "
            "RETURNING dq.domain"
        ),
        params or None,
    )
    deleted_rows = delete_q.fetchall() or []
    await db.commit()

    return {"deleted": len(deleted_rows)}
