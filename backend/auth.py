from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time

from pwdlib import PasswordHash

COOKIE_NAME = "receiptsift_session"
LEGACY_COOKIE_NAME = "clearledger_session"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_HASH = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASH.hash("clearledger-no-account-placeholder")


def normalize_email(value: str) -> str:
    email = value.strip().casefold()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("invalid_email")
    return email


def hash_password(password: str) -> str:
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASH.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def create_auth_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def auth_token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _secret(session_secret: str) -> bytes:
    value = session_secret or hashlib.sha256(b"clearledger-local-development-session").hexdigest()
    return value.encode()


def create_session(session_secret: str, user_id: str, days: int, session_version: int = 0) -> str:
    expires_at = int(time.time()) + max(days, 1) * 86400
    payload = f"{user_id}:{session_version}:{expires_at}".encode()
    signature = hmac.new(_secret(session_secret), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + b"." + signature).decode().rstrip("=")


def session_identity(token: str | None, session_secret: str) -> tuple[str, int] | None:
    if not token:
        return None
    try:
        padded = token + "=" * (-len(token) % 4)
        payload, signature = base64.urlsafe_b64decode(padded).split(b".", 1)
        expected = hmac.new(_secret(session_secret), payload, hashlib.sha256).digest()
        parts = payload.decode().rsplit(":", 2)
        if len(parts) == 2:
            user_id, expires_at = parts
            session_version = 0
        else:
            user_id, version, expires_at = parts
            session_version = int(version)
        if not hmac.compare_digest(signature, expected) or int(expires_at) < int(time.time()):
            return None
        return user_id, session_version
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


def session_user_id(token: str | None, session_secret: str) -> str | None:
    identity = session_identity(token, session_secret)
    return identity[0] if identity else None
