"""Domain Logs API - история парсинга доменов (персистентная, не привязана к run_id)."""

import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.adapters.db.session import get_db
from app.transport.routers.auth import get_current_user
from app.utils.authz import require_moderator
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

TABLE_NAME = "domain_logs"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    run_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    message TEXT,
    details JSONB DEFAULT '{{}}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_domain_logs_domain ON {TABLE_NAME} (domain);
CREATE INDEX IF NOT EXISTS idx_domain_logs_run_id ON {TABLE_NAME} (run_id);
CREATE INDEX IF NOT EXISTS idx_domain_logs_created_at ON {TABLE_NAME} (created_at DESC);
"""


class DomainLogEntry(BaseModel):
    id: int
    domain: str
    run_id: Optional[str] = None
    action: str
    message: Optional[str] = None
    details: Optional[dict] = None
    created_at: str


class DomainLogCreateRequest(BaseModel):
    domain: str
    run_id: Optional[str] = None
    action: str
    message: Optional[str] = None
    details: Optional[dict] = None


async def ensure_table(db: AsyncSession):
    """Create domain_logs table if it doesn't exist."""
    try:
        await db.execute(text(CREATE_TABLE_SQL))
        await db.commit()
    except Exception as e:
        logger.warning(f"domain_logs table creation: {e}")
        await db.rollback()


async def write_log(db: AsyncSession, domain: str, action: str, message: str = None,
                    run_id: str = None, details: dict = None):
    """Write a log entry for a domain (utility for other routers)."""
    try:
        await db.execute(
            text(
                f"INSERT INTO {TABLE_NAME} (domain, run_id, action, message, details) "
                "VALUES (:domain, :run_id, :action, :message, :details)"
            ),
            {
                "domain": domain,
                "run_id": run_id,
                "action": action,
                "message": message,
                "details": str(details) if details else None,
            },
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to write domain log: {e}")
        await db.rollback()


@router.get("/history/{domain}")
async def get_domain_history(
    domain: str,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get parsing history for a specific domain."""
    require_moderator(current_user)
    await ensure_table(db)

    result = await db.execute(
        text(
            f"SELECT id, domain, run_id, action, message, details, created_at "
            f"FROM {TABLE_NAME} WHERE domain = :domain "
            f"ORDER BY created_at DESC LIMIT :limit"
        ),
        {"domain": domain.lower(), "limit": limit},
    )
    rows = result.fetchall()
    return {
        "domain": domain,
        "total": len(rows),
        "logs": [
            {
                "id": r[0],
                "domain": r[1],
                "run_id": r[2],
                "action": r[3],
                "message": r[4],
                "details": r[5],
                "created_at": str(r[6]) if r[6] else None,
            }
            for r in rows
        ],
    }


@router.post("/log")
async def create_domain_log(
    req: DomainLogCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Manually create a domain log entry."""
    require_moderator(current_user)
    await ensure_table(db)
    await write_log(db, req.domain.lower(), req.action, req.message, req.run_id, req.details)
    return {"ok": True}


@router.get("/recent")
async def get_recent_logs(
    limit: int = Query(default=100, le=500),
    action: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get recent domain logs across all domains."""
    require_moderator(current_user)
    await ensure_table(db)

    if action:
        result = await db.execute(
            text(
                f"SELECT id, domain, run_id, action, message, details, created_at "
                f"FROM {TABLE_NAME} WHERE action = :action "
                f"ORDER BY created_at DESC LIMIT :limit"
            ),
            {"action": action, "limit": limit},
        )
    else:
        result = await db.execute(
            text(
                f"SELECT id, domain, run_id, action, message, details, created_at "
                f"FROM {TABLE_NAME} ORDER BY created_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
    rows = result.fetchall()
    return {
        "total": len(rows),
        "logs": [
            {
                "id": r[0],
                "domain": r[1],
                "run_id": r[2],
                "action": r[3],
                "message": r[4],
                "details": r[5],
                "created_at": str(r[6]) if r[6] else None,
            }
            for r in rows
        ],
    }
