"""Dependency FastAPI: autentikasi (JWT) dan penegakan izin (RBAC)."""
from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import Permission, has_permission
from app.core.security import decode_token
from app.models.user import User

_bearer = HTTPBearer(auto_error=True)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Kredensial tidak valid",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise _CREDENTIALS_EXC

    if payload.get("type") != "access":
        # Token MFA sementara tidak boleh dipakai untuk mengakses resource.
        raise _CREDENTIALS_EXC

    user_id = payload.get("sub")
    if user_id is None:
        raise _CREDENTIALS_EXC

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXC
    return user


def require_permission(permission: Permission) -> Callable[..., User]:
    """Factory dependency: menolak (403) bila role user tak punya izin."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' tidak memiliki izin '{permission}'",
            )
        return user

    return _dep
