"""Primitif keamanan: hashing password (bcrypt), JWT, dan TOTP (MFA).

Tidak ada panggilan jaringan. Semua lokal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt
import pyotp

from app.core.config import get_settings

settings = get_settings()

TokenType = Literal["access", "mfa"]

# bcrypt membatasi input 72 byte; kita encode dan potong secara aman.
_BCRYPT_MAX_BYTES = 72


# --- Password ---------------------------------------------------------------
def hash_password(plain: str) -> str:
    pw = plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        pw = plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT --------------------------------------------------------------------
def create_token(
    subject: str,
    role: str,
    token_type: TokenType = "access",
    ttl_minutes: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    if ttl_minutes is None:
        ttl_minutes = (
            settings.access_token_ttl_minutes
            if token_type == "access"
            else settings.mfa_token_ttl_minutes
        )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Mengembalikan payload. Melempar jwt.PyJWTError bila tidak valid/kedaluwarsa."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


# --- TOTP (MFA) -------------------------------------------------------------
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, username: str) -> str:
    """URI otpauth:// untuk didaftarkan ke aplikasi authenticator."""
    return pyotp.TOTP(secret).provisioning_uri(
        name=username, issuer_name=settings.totp_issuer
    )


def verify_totp(secret: str, code: str, valid_window: int = 1) -> bool:
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=valid_window)
