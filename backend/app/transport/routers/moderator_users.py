"""Router for moderator user access management."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.session import get_db
from app.transport.routers.auth import can_access_moderator_zone, get_current_user
from app.config import settings

router = APIRouter()


class UserAccessDTO(BaseModel):
    id: int
    username: str
    email: str | None = None
    role: str
    is_active: bool
    cabinet_access_enabled: bool


class UpdateCabinetAccessRequest(BaseModel):
    cabinet_access_enabled: bool


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


@router.get("/users", response_model=list[UserAccessDTO])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_moderator(current_user)
    from sqlalchemy import text

    result = await db.execute(
        text(
            "SELECT id, username, email, role, is_active, cabinet_access_enabled "
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

    updated = await db.execute(
        text(
            "UPDATE users SET cabinet_access_enabled = :enabled WHERE id = :id "
            "RETURNING id, username, email, role, is_active, cabinet_access_enabled"
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
    )
