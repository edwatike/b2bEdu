from __future__ import annotations

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Optional[Fernet]:
    key = (os.getenv("USER_SECRETS_FERNET_KEY") or "").strip()
    if not key:
        try:
            from app.config import settings

            key = (getattr(settings, "USER_SECRETS_FERNET_KEY", "") or "").strip()
        except Exception:
            key = ""
    if not key:
        return None
    try:
        raw = base64.urlsafe_b64decode(key.encode("utf-8"))
        if len(raw) != 32:
            return None
    except Exception:
        return None
    try:
        return Fernet(key.encode("utf-8"))
    except Exception:
        return None


def encrypt_user_secret(value: str) -> Optional[str]:
    if value is None:
        return None
    v = (value or "").strip()
    if not v:
        return None
    f = _get_fernet()
    if not f:
        return None
    token = f.encrypt(v.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_user_secret(value_encrypted: str) -> Optional[str]:
    if value_encrypted is None:
        return None
    t = (value_encrypted or "").strip()
    if not t:
        return None
    f = _get_fernet()
    if not f:
        return None
    try:
        raw = f.decrypt(t.encode("utf-8"))
        return raw.decode("utf-8")
    except (InvalidToken, Exception):
        return None
