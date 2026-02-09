"""Router for moderator user access management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.session import get_db
from app.transport.routers.auth import get_current_user
from app.utils.authz import require_moderator as _require_moderator
from app.config import settings
import logging
import time

router = APIRouter()
logger = logging.getLogger(__name__)

_DASHBOARD_STATS_CACHE: dict[str, object] = {"ts": 0.0, "value": None}
_DASHBOARD_STATS_TTL_SECONDS = 8.0

class UserAccessDTO(BaseModel):
    id: int
    username: str
    email: str | None = None
    role: str
    is_active: bool
    cabinet_access_enabled: bool
    organization_name: str | None = None


class UpdateCabinetAccessRequest(BaseModel):
    cabinet_access_enabled: bool


class CreateUserRequest(BaseModel):
    email: str
    organization_name: str | None = None


class ModeratorDashboardStatsDTO(BaseModel):
    domains_in_queue: int
    enrichment_domains_in_queue: int
    new_suppliers: int
    new_suppliers_week: int
    active_runs: int
    blacklist_count: int
    open_tasks: int




def _normalize_task_status(status_value: str) -> str:
    s = str(status_value or "").strip().lower()
    if s in {"done", "completed"}:
        return "completed"
    if s in {"running", "processing"}:
        return "running"
    if s in {"failed", "error"}:
        return "failed"
    if s == "new":
        return "new"
    return s or "new"


def _aggregate_task_status(
    run_statuses: list[str],
    existing_status: str,
    all_domains_resolved: bool | None = None,
) -> str:
    statuses = [_normalize_task_status(x) for x in (run_statuses or [])]
    statuses = [s for s in statuses if s]
    if any(s == "failed" for s in statuses):
        return "failed"
    if any(s == "running" for s in statuses):
        return "running"
    if statuses and all(s == "completed" for s in statuses):
        if all_domains_resolved is False:
            return "running"
        return "completed"
    return _normalize_task_status(existing_status)


async def _ensure_users_columns(db: AsyncSession) -> None:
    from sqlalchemy import text
    try:
        await db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_name TEXT"))
    except Exception:
        pass


@router.get("/tasks")
async def list_moderator_tasks(
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    from sqlalchemy import text

    _require_moderator(current_user)
    try:
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
        await db.execute(text("ALTER TABLE moderator_tasks ADD COLUMN IF NOT EXISTS title TEXT"))
    except Exception:
        pass

    q = await db.execute(
        text(
            "SELECT t.id, t.request_id, t.created_by, t.title, t.status, t.source, t.depth, t.created_at, r.title AS request_title "
            "FROM moderator_tasks t "
            "LEFT JOIN parsing_requests r ON r.id = t.request_id "
            "ORDER BY t.id DESC LIMIT :limit OFFSET :offset"
        ),
        {"limit": int(limit), "offset": int(offset)},
    )
    rows = q.fetchall() or []

    request_ids = list(dict.fromkeys([int(r[1]) for r in rows if r and r[1] is not None]))
    runs_by_request: dict[int, list[dict]] = {int(rid): [] for rid in request_ids}
    if request_ids:
        runs_q = await db.execute(
            text(
                "SELECT request_id, run_id, status, created_at, process_log "
                "FROM parsing_runs "
                "WHERE request_id = ANY(:rids) "
                "ORDER BY created_at ASC"
            ),
            {"rids": request_ids},
        )
        run_rows = runs_q.fetchall() or []
        for rr in run_rows:
            rid = int(rr[0])
            run_id = str(rr[1])
            status = str(rr[2] or "")
            created_at = rr[3].isoformat() if rr[3] else None
            process_log = rr[4]
            keyword = None
            try:
                if isinstance(process_log, dict):
                    keyword = process_log.get("keyword")
                elif isinstance(process_log, str) and process_log.strip():
                    import json

                    keyword = (json.loads(process_log) or {}).get("keyword")
            except Exception:
                keyword = None

            item = {
                "run_id": run_id,
                "status": status,
                "created_at": created_at,
                "keyword": keyword,
            }
            if rid not in runs_by_request:
                runs_by_request[rid] = []
            runs_by_request[rid].append(item)

    # Check which requests have ALL domains resolved (supplier/reseller)
    # A task is "completed" only if every domain across all its runs is a supplier or reseller.
    request_domains_resolved: dict[int, bool] = {}
    if request_ids:
        try:
            check_q = await db.execute(
                text(
                    "SELECT pr.request_id, "
                    "  COUNT(DISTINCT replace(lower(dq.domain), 'www.', '')) AS total_domains, "
                    "  COUNT(DISTINCT CASE WHEN ("
                    "    EXISTS (SELECT 1 FROM moderator_suppliers ms "
                    "            LEFT JOIN supplier_domains sd ON sd.supplier_id = ms.id "
                    "            WHERE replace(lower(COALESCE(sd.domain, ms.domain, '')), 'www.', '') = replace(lower(dq.domain), 'www.', ''))"
                    "  ) THEN replace(lower(dq.domain), 'www.', '') END) AS resolved_domains "
                    "FROM parsing_runs pr "
                    "JOIN domains_queue dq ON dq.parsing_run_id = pr.run_id "
                    "WHERE pr.request_id = ANY(:rids) "
                    "GROUP BY pr.request_id"
                ),
                {"rids": request_ids},
            )
            for cr in (check_q.fetchall() or []):
                rid = int(cr[0])
                total_d = int(cr[1] or 0)
                resolved_d = int(cr[2] or 0)
                request_domains_resolved[rid] = (total_d > 0 and resolved_d >= total_d)
        except Exception:
            pass

    # Aggregate and persist task statuses based on parsing run statuses + domain resolution.
    task_updates: list[tuple[int, str]] = []
    for r in rows:
        try:
            task_id = int(r[0])
            rid = int(r[1])
            current_status = str(r[4] or "new")
            run_statuses = [str(x.get("status") or "") for x in (runs_by_request.get(rid) or [])]
            all_resolved = request_domains_resolved.get(rid)
            desired = _aggregate_task_status(run_statuses, current_status, all_domains_resolved=all_resolved)
            if _normalize_task_status(current_status) != _normalize_task_status(desired):
                task_updates.append((task_id, desired))
        except Exception:
            continue

    if task_updates:
        for task_id, desired in task_updates:
            await db.execute(
                text("UPDATE moderator_tasks SET status = :status WHERE id = :id"),
                {"status": str(desired), "id": int(task_id)},
            )
        try:
            await db.commit()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass

    out = []
    for r in rows:
        rid = int(r[1])
        current_status = str(r[4] or "new")
        run_statuses = [str(x.get("status") or "") for x in (runs_by_request.get(rid) or [])]
        all_resolved = request_domains_resolved.get(rid)
        derived_status = _aggregate_task_status(run_statuses, current_status, all_domains_resolved=all_resolved)
        out.append(
            {
                "id": int(r[0]),
                "request_id": rid,
                "created_by": int(r[2]),
                "title": (r[3] if (r[3] and str(r[3]).strip()) else r[8]),
                "status": derived_status,
                "source": str(r[5] or "google"),
                "depth": int(r[6] or 30),
                "created_at": r[7].isoformat() if r[7] else None,
                "request_title": r[8],
                "parsing_runs": runs_by_request.get(rid, []),
            }
        )

    return out


@router.get("/dashboard-stats", response_model=ModeratorDashboardStatsDTO)
async def get_moderator_dashboard_stats(
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text

    _require_moderator(current_user)
    ts = time.monotonic()
    cached = _DASHBOARD_STATS_CACHE.get("value")
    cached_ts = float(_DASHBOARD_STATS_CACHE.get("ts") or 0.0)
    if cached and (ts - cached_ts) < _DASHBOARD_STATS_TTL_SECONDS:
        return cached
    try:
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
    except Exception:
        pass

    # Single round-trip stats query for fast dashboard load.
    from app.transport.routers import domains_queue as domains_queue_router

    dq_expr = domains_queue_router._root_domain_sql("dq.domain")
    bl_expr = domains_queue_router._root_domain_sql("b.domain")
    s_expr = domains_queue_router._root_domain_sql("s.domain")
    sd_expr = domains_queue_router._root_domain_sql("sd.domain")

    q = await db.execute(
        text(
            "WITH normalized_domains AS ("
            f"  SELECT {dq_expr} AS d, "
            "         MAX(dq.created_at) AS last_seen_at, "
            "         COUNT(*) AS occurrences "
            "  FROM domains_queue dq "
            "  GROUP BY d "
            "),"
            "blacklisted AS ("
            f"  SELECT DISTINCT {bl_expr} AS d FROM blacklist b WHERE b.domain IS NOT NULL"
            "),"
            "supplier_domains_all AS ("
            f"  SELECT DISTINCT {s_expr} AS d FROM moderator_suppliers s "
            "  WHERE s.domain IS NOT NULL AND COALESCE(s.data_status, '') NOT IN ('requires_moderation', '')"
            "  UNION "
            f"  SELECT DISTINCT {sd_expr} AS d FROM supplier_domains sd "
            "  INNER JOIN moderator_suppliers ms ON ms.id = sd.supplier_id "
            "  WHERE sd.domain IS NOT NULL AND COALESCE(ms.data_status, '') NOT IN ('requires_moderation', '')"
            "),"
            "pending AS ("
            "  SELECT * FROM normalized_domains "
            "  WHERE d IS NOT NULL AND d <> '' "
            "    AND d NOT IN (SELECT d FROM blacklisted) "
            "    AND d NOT IN (SELECT d FROM supplier_domains_all)"
            ") "
            "SELECT "
            "  (SELECT COUNT(*) FROM moderator_suppliers) AS new_suppliers, "
            "  (SELECT COUNT(*) FROM moderator_suppliers WHERE created_at >= NOW() - INTERVAL '7 days') AS new_suppliers_week, "
            "  (SELECT COUNT(*) FROM blacklist) AS blacklist_count, "
            "  (SELECT COUNT(*) FROM parsing_runs WHERE status = 'running') AS active_runs, "
            "  (SELECT COUNT(*) FROM moderator_tasks WHERE lower(status) NOT IN ('done','completed','closed')) AS open_tasks, "
            "  (SELECT COUNT(*) FROM pending) AS domains_in_queue, "
            "  (SELECT COALESCE(SUM(rem), 0) FROM ("
            "      SELECT GREATEST(0, "
            "        (SELECT COUNT(DISTINCT dq.domain)::int FROM domains_queue dq WHERE dq.parsing_run_id = pr.run_id) "
            "        - COALESCE(NULLIF(pr.process_log->'domain_parser_auto'->>'processed','')::int, 0)"
            "      ) AS rem "
            "      FROM parsing_runs pr "
            "      WHERE COALESCE(pr.process_log->'domain_parser_auto'->>'status','') IN ('queued','running')"
            "    ) q"
            "  ) AS enrichment_domains_in_queue"
        )
    )
    row = q.fetchone()
    if not row:
        empty = ModeratorDashboardStatsDTO(
            domains_in_queue=0,
            enrichment_domains_in_queue=0,
            new_suppliers=0,
            new_suppliers_week=0,
            active_runs=0,
            blacklist_count=0,
            open_tasks=0,
        )
        _DASHBOARD_STATS_CACHE["ts"] = ts
        _DASHBOARD_STATS_CACHE["value"] = empty
        return empty

    result = ModeratorDashboardStatsDTO(
        domains_in_queue=int(row[5] or 0),
        enrichment_domains_in_queue=int(row[6] or 0),
        new_suppliers=int(row[0] or 0),
        new_suppliers_week=int(row[1] or 0),
        blacklist_count=int(row[2] or 0),
        active_runs=int(row[3] or 0),
        open_tasks=int(row[4] or 0),
    )
    _DASHBOARD_STATS_CACHE["ts"] = ts
    _DASHBOARD_STATS_CACHE["value"] = result
    return result


@router.get("/users", response_model=list[UserAccessDTO])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_moderator(current_user)
    from sqlalchemy import text
    await _ensure_users_columns(db)
    result = await db.execute(
        text(
            "SELECT id, username, email, role, is_active, cabinet_access_enabled, organization_name "
            "FROM users ORDER BY id DESC"
        )
    )
    rows = result.fetchall() or []
    return [
        UserAccessDTO(
            id=int(r[0]),
            username=str(r[1]),
            email=str(r[2]) if r[2] is not None else None,
            role=str(r[3]),
            is_active=bool(r[4]),
            cabinet_access_enabled=bool(r[5]),
            organization_name=str(r[6]) if r[6] is not None else None,
        )
        for r in rows
    ]


@router.patch("/users/{user_id}/cabinet-access", response_model=UserAccessDTO)
async def update_user_cabinet_access(
    user_id: int,
    payload: UpdateCabinetAccessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_moderator(current_user)
    from sqlalchemy import text

    await _ensure_users_columns(db)
    updated = await db.execute(
        text(
            "UPDATE users SET cabinet_access_enabled = :enabled WHERE id = :id "
            "RETURNING id, username, email, role, is_active, cabinet_access_enabled, organization_name"
        ),
        {"enabled": bool(payload.cabinet_access_enabled), "id": int(user_id)},
    )
    row = updated.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.commit()

    return UserAccessDTO(
        id=int(row[0]),
        username=str(row[1]),
        email=str(row[2]) if row[2] is not None else None,
        role=str(row[3]),
        is_active=bool(row[4]),
        cabinet_access_enabled=bool(row[5]),
        organization_name=str(row[6]) if row[6] is not None else None,
    )


@router.post("/users", response_model=UserAccessDTO, status_code=201)
async def create_user(
    payload: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create user with email (for Yandex OAuth access)."""
    _require_moderator(current_user)
    from sqlalchemy import text
    from app.utils.auth import get_password_hash
    import secrets
    import re

    await _ensure_users_columns(db)

    email = str(payload.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Некорректный email")

    # Check for existing user
    existing = await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})
    if existing.fetchone():
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")

    username_base = re.sub(r"[^a-zA-Z0-9_\\.-]", "_", email.split("@", 1)[0])[:30] or "user"
    username = f"{username_base}_{secrets.token_hex(3)}"
    hashed_password = get_password_hash(secrets.token_urlsafe(32))
    organization_name = str(payload.organization_name or "").strip() or None

    created = await db.execute(
        text(
            "INSERT INTO users (username, email, hashed_password, role, is_active, cabinet_access_enabled, auth_method, organization_name) "
            "VALUES (:username, :email, :hashed_password, :role, :is_active, :cabinet_access_enabled, :auth_method, :organization_name) "
            "RETURNING id, username, email, role, is_active, cabinet_access_enabled, organization_name"
        ),
        {
            "username": username,
            "email": email,
            "hashed_password": hashed_password,
            "role": "user",
            "is_active": True,
            "cabinet_access_enabled": True,
            "auth_method": "invite",
            "organization_name": organization_name,
        },
    )
    await db.commit()
    row = created.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Не удалось создать пользователя")

    return UserAccessDTO(
        id=int(row[0]),
        username=str(row[1]),
        email=str(row[2]) if row[2] is not None else None,
        role=str(row[3]),
        is_active=bool(row[4]),
        cabinet_access_enabled=bool(row[5]),
        organization_name=str(row[6]) if row[6] is not None else None,
    )


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_moderator(current_user)
    from sqlalchemy import text

    await _ensure_users_columns(db)
    res = await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": int(user_id)})
    await db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")
