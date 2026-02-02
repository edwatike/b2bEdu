from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict, Any

import os
import re
import time
import secrets
import hashlib
import smtplib
from email.message import EmailMessage

from app.adapters.db.session import get_db
from app.utils.auth import verify_password, get_password_hash, create_access_token, verify_token

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


def _get_master_moderator_email() -> str:
    return (os.getenv("MODERATOR_MASTER_EMAIL") or "edwatik@yandex.ru").strip().lower()


def is_master_moderator_email(email: str | None) -> bool:
    if not email:
        return False
    return email.strip().lower() == _get_master_moderator_email()


def can_access_moderator_zone(user: dict) -> bool:
    return is_master_moderator_email(user.get("email")) and str(user.get("role") or "") == "moderator"

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


class OtpRequest(BaseModel):
    email: str


class OtpVerify(BaseModel):
    email: str
    code: str


_otp_storage: Dict[str, Dict[str, Any]] = {}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _hash_code(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()


def _send_otp_email(to_email: str, code: str) -> None:
    import logging
    logger = logging.getLogger(__name__)
    
    # Логируем OTP код для отладки
    logger.info(f"OTP code for {to_email}: {code}")
    print(f"[OTP] OTP CODE FOR {to_email}: {code}")
    
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port_raw = os.getenv("SMTP_PORT", "465")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_security = (os.getenv("SMTP_SECURITY", "ssl") or "ssl").lower()
    smtp_from = os.getenv("SMTP_FROM") or smtp_user

    if not smtp_host or not smtp_user or not smtp_password or not smtp_from:
        # В development режиме просто логируем код
        if os.getenv("ENV", "development") == "development":
            logger.warning("SMTP not configured, OTP code logged only")
            return
        raise RuntimeError("SMTP is not configured")

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT must be a number") from exc

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg["Subject"] = "Код для входа в личный кабинет"
    msg.set_content(
        "Ваш одноразовый код для входа: "
        f"{code}\n\n"
        "Код действует 10 минут. Если вы не запрашивали вход — просто игнорируйте это письмо.\n"
    )

    if smtp_security in {"ssl", "smtps"}:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.ehlo()
        if smtp_security in {"starttls", "tls"}:
            server.starttls()
            server.ehlo()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Получение текущего пользователя по токену"""
    from sqlalchemy import text
    
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

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """Вход пользователя"""
    from sqlalchemy import text
    
    # Ищем пользователя через raw SQL
    result = await db.execute(
        text("SELECT id, username, email, hashed_password, role, is_active FROM users WHERE username = :username"),
        {"username": user_credentials.username}
    )
    user_row = result.fetchone()
    
    # Проверяем пароль
    if not user_row or not verify_password(user_credentials.password, user_row[3]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user_row[5]:  # is_active
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Создаем токен
    access_token = create_access_token(data={
        "sub": user_row[1],
        "id": user_row[0],
        "username": user_row[1],
        "role": user_row[4],
    })
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user_row[0],
            "username": user_row[1],
            "email": user_row[2],
            "role": user_row[4]
        }
    }


@router.post("/otp/request")
async def request_otp(payload: OtpRequest):
    raise HTTPException(status_code=404, detail="Not found")
    email = _normalize_email(payload.email)
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email")

    now = int(time.time())
    record = _otp_storage.get(email)
    if record and now - int(record.get("sent_at", 0)) < 60:
        raise HTTPException(status_code=429, detail="OTP recently sent. Please wait.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    code_hash = _hash_code(code, salt)

    _otp_storage[email] = {
        "code_hash": code_hash,
        "salt": salt,
        "expires_at": now + 10 * 60,
        "attempts": 0,
        "sent_at": now,
    }

    try:
        _send_otp_email(email, code)
    except Exception:
        _otp_storage.pop(email, None)
        raise HTTPException(status_code=500, detail="Failed to send OTP")

    return {"success": True}


@router.post("/otp/verify", response_model=Token)
async def verify_otp(payload: OtpVerify, db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=404, detail="Not found")
    from sqlalchemy import text

    email = _normalize_email(payload.email)
    code = (payload.code or "").strip()

    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email")
    if not re.match(r"^\d{6}$", code):
        raise HTTPException(status_code=400, detail="Invalid code")

    now = int(time.time())
    record = _otp_storage.get(email)
    if not record:
        raise HTTPException(status_code=400, detail="OTP not requested")

    if now > int(record.get("expires_at", 0)):
        _otp_storage.pop(email, None)
        raise HTTPException(status_code=400, detail="OTP expired")

    if int(record.get("attempts", 0)) >= 5:
        _otp_storage.pop(email, None)
        raise HTTPException(status_code=429, detail="Too many attempts")

    expected_hash = record.get("code_hash")
    salt = record.get("salt")
    if not expected_hash or not salt:
        _otp_storage.pop(email, None)
        raise HTTPException(status_code=400, detail="OTP invalid")

    if _hash_code(code, salt) != expected_hash:
        record["attempts"] = int(record.get("attempts", 0)) + 1
        _otp_storage[email] = record
        raise HTTPException(status_code=400, detail="Incorrect code")

    _otp_storage.pop(email, None)

    result = await db.execute(
        text("SELECT id, username, email, role, is_active, cabinet_access_enabled FROM users WHERE email = :email"),
        {"email": email},
    )
    user_row = result.fetchone()

    if user_row is None:
        username_base = re.sub(r"[^a-zA-Z0-9_\.-]", "_", email.split("@", 1)[0])[:30] or "user"
        username = f"{username_base}_{secrets.token_hex(3)}"
        hashed_password = get_password_hash(secrets.token_urlsafe(32))

        created = await db.execute(
            text(
                "INSERT INTO users (username, email, hashed_password, role, is_active) "
                "VALUES (:username, :email, :hashed_password, :role, :is_active) "
                "RETURNING id, username, email, role, is_active, cabinet_access_enabled"
            ),
            {
                "username": username,
                "email": email,
                "hashed_password": hashed_password,
                "role": "user",
                "is_active": True,
            },
        )
        await db.commit()
        user_row = created.fetchone()
    else:
        if not user_row[4]:
            raise HTTPException(status_code=400, detail="Inactive user")

    access_token = create_access_token(data={
        "sub": user_row[1],
        "id": user_row[0],
        "username": user_row[1],
        "role": user_row[3],
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user_row[0],
            "username": user_row[1],
            "email": user_row[2],
            "role": user_row[3],
        },
    }

@router.post("/logout")
async def logout():
    """Выход пользователя (на стороне клиента нужно удалить токен)"""
    return {"message": "Successfully logged out"}


@router.get("/status")
async def auth_status(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Проверка статуса аутентификации"""
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


@router.post("/yandex-oauth", response_model=Token)
async def yandex_oauth_login(payload: dict, db: AsyncSession = Depends(get_db)):
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
        print(f"✅ New user registered via Yandex OAuth: {email}")
        
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
        print(f"✅ Existing user logged in via Yandex OAuth: {email}")
        
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