"""Centralized authorization guards.

Single source of truth for role-based access control.
All routers MUST import from here instead of defining local copies.
"""
from fastapi import HTTPException, status


def require_moderator(current_user: dict) -> None:
    """Require moderator or admin role. No dev-bypass.

    Raises HTTPException 403 if the user does not have moderator/admin access.
    """
    from app.transport.routers.auth import can_access_moderator_zone

    if not can_access_moderator_zone(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: moderator or admin role required",
        )
