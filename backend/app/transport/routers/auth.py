from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict, Any

import os
import re

from app.adapters.db.session import get_db
from app.utils.auth import get_password_hash, create_access_token, verify_token
from app.utils.rate_limit import limiter, AUTH_LIMIT

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer(auto_error=False)


def _is_auth_bypass_enabled() -> bool:
    return str(os.getenv("B2B_AUTH_BYPASS", "")).strip().lower() in {"1", "true", "yes", "on"}


def _get_master_moderator_email() -> str:
    return (os.getenv("MODERATOR_MASTER_EMAIL") or "edwatik@yandex.ru").strip().lower()


def is_master_moderator_email(email: str | None) -> bool:
    if not email:
        return False
    return email.strip().lower() == _get_master_moderator_email()


def can_access_moderator_zone(user: dict) -> bool:
    role = str(user.get("role") or "")
    if role in {"admin", "moderator"}:
        return True
    return is_master_moderator_email(user.get("email")) and role == "moderator"

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Получение текущего пользователя по токену"""
    from sqlalchemy import text

    if _is_auth_bypass_enabled():
        return {
            "id": 0,
            "username": "launcher-noauth",
            "email": "noauth@local",
            "role": "admin",
            "is_active": True,
            "cabinet_access_enabled": True,
            "auth_method": "launcher_noauth",
        }

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Получаем пользователя из БД через raw SQL
    result = await db.execute(
        text(
            "SELECT id, username, email, hashed_password, role, is_active, cabinet_access_enabled, auth_method "
            "FROM users WHERE username = :username"
        ),
        {"username": username},
    )
    user_row = result.fetchone()
    
    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "id": user_row[0],
        "username": user_row[1], 
        "email": user_row[2],
        "role": user_row[4],
        "is_active": user_row[5],
        "cabinet_access_enabled": bool(user_row[6]) if user_row[6] is not None else False,
        "auth_method": user_row[7] if len(user_row) > 7 else None,
    }


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Return current user plus computed permissions.

    Backend is the source of truth for role/permissions.
    """
    return {
        "authenticated": True,
        "user": {
            "id": current_user.get("id"),
            "username": current_user.get("username"),
            "email": current_user.get("email"),
            "role": current_user.get("role"),
            "auth_method": current_user.get("auth_method"),
            "cabinet_access_enabled": bool(current_user.get("cabinet_access_enabled")),
            "can_access_moderator": can_access_moderator_zone(current_user),
            "can_switch_zones": can_access_moderator_zone(current_user),
        },
    }


@router.post("/logout")
@limiter.limit(AUTH_LIMIT)
async def logout(request: Request):
    """Выход пользователя (на стороне клиента нужно удалить токен)"""
    return {"message": "Successfully logged out"}


@router.get("/status")
@limiter.limit(AUTH_LIMIT)
async def auth_status(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Проверка статуса аутентификации"""
    if _is_auth_bypass_enabled():
        return {
            "authenticated": True,
            "user": {
                "username": "launcher-noauth",
                "role": "admin",
                "can_access_moderator": True,
            },
        }

    try:
        # Проверяем токен в cookie
        auth_token = request.cookies.get("auth_token")
        if not auth_token:
            # Проверяем Authorization header
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                auth_token = auth_header[7:]
        
        if not auth_token:
            return {
                "authenticated": False,
                "user": None,
            }
        
        # Создаем credentials для get_current_user
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth_token)
        user = await get_current_user(credentials, db)
        
        return {
            "authenticated": True,
            "user": {
                "username": user["username"],
                "role": user["role"],
            }
        }
    except HTTPException:
        return {
            "authenticated": False,
            "user": None,
        }
    except Exception as e:
        return {
            "authenticated": False,
            "user": None,
        }


@router.post("/github-oauth", response_model=Token)
@limiter.limit(AUTH_LIMIT)
async def github_oauth_login(request: Request, payload: dict, db: AsyncSession = Depends(get_db)):
    """
    Регистрация или авторизация пользователя через GitHub OAuth
    """
    import httpx
    
    github_access_token = payload.get("access_token")
    if not github_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub access token is required"
        )
    
    # Получаем информацию о пользователе из GitHub
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {github_access_token}"}
        )
        if user_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch GitHub user data"
            )
        
        github_user = user_response.json()
        github_id = github_user.get("id")
        username = github_user.get("login")
        email = github_user.get("email")
        
        # Если email не публичный, получаем через emails API
        if not email:
            emails_response = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {github_access_token}"}
            )
            if emails_response.status_code == 200:
                emails = emails_response.json()
                primary_email = next((e for e in emails if e.get("primary")), emails[0])
                email = primary_email.get("email")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required for registration"
            )
    
    email = _normalize_email(email)
    
    # Проверяем существующего пользователя по email
    result = await db.execute(
        ("SELECT id, username, email, role, is_active, cabinet_access_enabled, auth_method "
         "FROM users WHERE email = :email"),
        {"email": email},
    )
    user_row = result.fetchone()
    
    if user_row is None:
        # Создаем нового пользователя
        role = "moderator" if is_master_moderator_email(email) else "user"
        cabinet_access_enabled = is_master_moderator_email(email)
        
        await db.execute(
            ("INSERT INTO users (username, email, role, is_active, cabinet_access_enabled, auth_method, github_id) "
             "VALUES (:username, :email, :role, :is_active, :cabinet_access_enabled, :auth_method, :github_id)"),
            {
                "username": username,
                "email": email,
                "role": role,
                "is_active": True,
                "cabinet_access_enabled": cabinet_access_enabled,
                "auth_method": "github_oauth",
                "github_id": github_id,
            },
        )
        await db.commit()
        
        user_data = {
            "id": github_id,
            "username": username,
            "email": email,
            "role": role,
            "auth_method": "github_oauth"
        }
    else:
        # Обновляем существующего пользователя
        await db.execute(
            ("UPDATE users SET github_id = :github_id, auth_method = :auth_method "
             "WHERE email = :email"),
            {
                "github_id": github_id,
                "auth_method": "github_oauth",
                "email": email,
            },
        )
        await db.commit()
        
        user_data = {
            "id": user_row[0],
            "username": user_row[1],
            "email": user_row[2],
            "role": user_row[3],
            "auth_method": "github_oauth"
        }
    
    # Создаем JWT токен
    access_token = create_access_token(data={"sub": user_data["email"]})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    }


@router.post("/yandex-oauth", response_model=Token)
@limiter.limit(AUTH_LIMIT)
async def yandex_oauth_login(request: Request, payload: dict, db: AsyncSession = Depends(get_db)):
    """
    Регистрация или авторизация пользователя через Яндекс OAuth
    """
    import secrets
    import re
    
    email = payload.get("email", "").strip().lower()
    yandex_access_token = payload.get("yandex_access_token", "")
    yandex_refresh_token = payload.get("yandex_refresh_token", "")
    expires_in = payload.get("expires_in", 3600)
    
    if not email or not yandex_access_token:
        raise HTTPException(status_code=400, detail="Missing email or access token")
    
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    # Используем raw SQL для обхода кэша SQLAlchemy
    from sqlalchemy import text
    from datetime import datetime, timedelta, timezone
    
    master_email = _get_master_moderator_email()

    # Проверяем, есть ли пользователь в БД
    result = await db.execute(
        text("SELECT id, username, email, role, is_active, cabinet_access_enabled FROM users WHERE email = :email"),
        {"email": email},
    )
    user_row = result.fetchone()
    
    if user_row is None:
        # Создаем нового пользователя через raw SQL
        username_base = re.sub(r"[^a-zA-Z0-9_\.-]", "_", email.split("@", 1)[0])[:30] or "user"
        username = f"{username_base}_{secrets.token_hex(3)}"
        hashed_password = get_password_hash(secrets.token_urlsafe(32))

        expires_at = None
        try:
            expires_in_int = int(expires_in)
        except Exception:
            expires_in_int = 3600
        if expires_in_int and expires_in_int > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_int)
        
        role = "moderator" if email == master_email else "user"
        cabinet_access_enabled = True

        created = await db.execute(
            text(
                "INSERT INTO users (username, email, hashed_password, role, is_active, cabinet_access_enabled, auth_method, yandex_access_token, yandex_refresh_token, yandex_token_expires_at) "
                "VALUES (:username, :email, :hashed_password, :role, :is_active, :cabinet_access_enabled, :auth_method, :yandex_access_token, :yandex_refresh_token, :yandex_token_expires_at) "
                "RETURNING id, username, email, role, is_active, cabinet_access_enabled"
            ),
            {
                "username": username,
                "email": email,
                "hashed_password": hashed_password,
                "role": role,
                "is_active": True,
                "cabinet_access_enabled": cabinet_access_enabled,
                "auth_method": "yandex_oauth",
                "yandex_access_token": yandex_access_token,
                "yandex_refresh_token": yandex_refresh_token or None,
                "yandex_token_expires_at": expires_at,
            },
        )
        await db.commit()
        user_row = created.fetchone()
        
        # Логируем создание нового пользователя
        import logging
        logging.getLogger(__name__).info(f"New user registered via Yandex OAuth: {email}")
        
    else:
        expires_at = None
        try:
            expires_in_int = int(expires_in)
        except Exception:
            expires_in_int = 3600
        if expires_in_int and expires_in_int > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_int)

        # Обновляем last_login и OAuth поля для существующего пользователя
        await db.execute(
            text("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE email = :email"),
            {"email": email},
        )
        role = "moderator" if email == master_email else str(user_row[3] or "user")
        cabinet_access_enabled = True

        await db.execute(
            text(
                "UPDATE users SET "
                "auth_method = :auth_method, "
                "yandex_access_token = :yandex_access_token, "
                "yandex_refresh_token = :yandex_refresh_token, "
                "yandex_token_expires_at = :yandex_token_expires_at, "
                "cabinet_access_enabled = :cabinet_access_enabled, "
                "role = :role "
                "WHERE email = :email"
            ),
            {
                "email": email,
                "auth_method": "yandex_oauth",
                "yandex_access_token": yandex_access_token,
                "yandex_refresh_token": yandex_refresh_token or None,
                "yandex_token_expires_at": expires_at,
                "cabinet_access_enabled": cabinet_access_enabled,
                "role": role,
            },
        )
        await db.commit()

        # IMPORTANT: re-read the user row after UPDATE, otherwise we may use stale
        # cabinet_access_enabled from the original SELECT above.
        result = await db.execute(
            text("SELECT id, username, email, role, is_active, cabinet_access_enabled FROM users WHERE email = :email"),
            {"email": email},
        )
        user_row = result.fetchone()
        
        # Логируем вход существующего пользователя
        import logging
        logging.getLogger(__name__).info(f"Existing user logged in via Yandex OAuth: {email}")
        
        if not user_row[4]:  # is_active
            raise HTTPException(status_code=400, detail="User account is inactive")

    # Access control for user cabinet
    # user_row: id, username, email, role, is_active, cabinet_access_enabled
    if str(user_row[3]) == "user" and not bool(user_row[5]):
        raise HTTPException(status_code=403, detail="Cabinet access is not enabled for this user")
    
    # Создаем JWT токен
    access_token = create_access_token(data={
        "sub": user_row[1],
        "id": user_row[0],
        "username": user_row[1],
        "email": user_row[2],
        "role": user_row[3],
        "auth_method": "yandex_oauth"
    })
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": {
            "id": user_row[0],
            "username": user_row[1],
            "email": user_row[2],
            "role": user_row[3],
            "auth_method": "yandex_oauth"
        },
    }
