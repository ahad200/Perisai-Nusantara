"""Router autentikasi: login (password + TOTP MFA) dan pengelolaan MFA."""
from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import (
    create_token,
    decode_token,
    generate_totp_secret,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MfaEnableRequest,
    MfaSetupResponse,
    MfaVerifyRequest,
    TokenResponse,
)
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()


def _issue_access(user: User) -> TokenResponse:
    token = create_token(subject=str(user.id), role=user.role, token_type="access")
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = _get_user_by_username(db, body.username)
    if user is None or not user.is_active or not verify_password(body.password, user.hashed_password):
        audit.record(
            db,
            action="auth.login.failure",
            actor_type="user",
            actor_id=body.username,
            object_type="user",
            object_id=body.username,
            payload={"reason": "username/password salah atau akun nonaktif"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Username atau password salah"
        )

    if user.mfa_enabled:
        if body.otp_code:
            if not verify_totp(user.totp_secret or "", body.otp_code):
                audit.record(
                    db,
                    action="auth.login.mfa_failure",
                    actor_type="user",
                    actor_id=user.username,
                    object_type="user",
                    object_id=str(user.id),
                    payload={"reason": "kode OTP salah"},
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Kode OTP salah"
                )
            tok = _issue_access(user)
            audit.record(
                db,
                action="auth.login.success",
                actor_type="user",
                actor_id=user.username,
                object_type="user",
                object_id=str(user.id),
                payload={"mfa": True},
            )
            return LoginResponse(access_token=tok.access_token, token_type="bearer")

        # MFA aktif tapi OTP belum diberikan -> tantangan.
        mfa_token = create_token(subject=str(user.id), role=user.role, token_type="mfa")
        audit.record(
            db,
            action="auth.login.mfa_challenge",
            actor_type="user",
            actor_id=user.username,
            object_type="user",
            object_id=str(user.id),
            payload={},
        )
        return LoginResponse(mfa_required=True, mfa_token=mfa_token)

    # Tanpa MFA.
    tok = _issue_access(user)
    audit.record(
        db,
        action="auth.login.success",
        actor_type="user",
        actor_id=user.username,
        object_type="user",
        object_id=str(user.id),
        payload={"mfa": False},
    )
    return LoginResponse(access_token=tok.access_token, token_type="bearer")


@router.post("/mfa", response_model=TokenResponse)
def complete_mfa(body: MfaVerifyRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        payload = decode_token(body.mfa_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="mfa_token tidak valid")
    if payload.get("type") != "mfa":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tipe token salah")

    user = db.get(User, int(payload.get("sub", 0)))
    if user is None or not user.is_active or not user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tidak dapat diproses")

    if not verify_totp(user.totp_secret or "", body.otp_code):
        audit.record(
            db,
            action="auth.login.mfa_failure",
            actor_type="user",
            actor_id=user.username,
            object_type="user",
            object_id=str(user.id),
            payload={"reason": "kode OTP salah (step mfa)"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kode OTP salah")

    audit.record(
        db,
        action="auth.login.success",
        actor_type="user",
        actor_id=user.username,
        object_type="user",
        object_id=str(user.id),
        payload={"mfa": True, "step": "mfa"},
    )
    return _issue_access(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MfaSetupResponse:
    """Membuat/mengambil secret TOTP. MFA belum aktif sampai /mfa/enable diverifikasi."""
    if not user.totp_secret:
        user.totp_secret = generate_totp_secret()
        db.add(user)
        db.commit()
        db.refresh(user)
    audit.record(
        db,
        action="auth.mfa.setup",
        actor_type="user",
        actor_id=user.username,
        object_type="user",
        object_id=str(user.id),
        payload={},
    )
    return MfaSetupResponse(
        secret=user.totp_secret,
        otpauth_uri=totp_provisioning_uri(user.totp_secret, user.username),
    )


@router.post("/mfa/enable", status_code=status.HTTP_200_OK)
def mfa_enable(
    body: MfaEnableRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Jalankan /auth/mfa/setup dulu"
        )
    if not verify_totp(user.totp_secret, body.otp_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kode OTP salah")

    user.mfa_enabled = True
    db.add(user)
    db.commit()
    audit.record(
        db,
        action="auth.mfa.enable",
        actor_type="user",
        actor_id=user.username,
        object_type="user",
        object_id=str(user.id),
        payload={},
    )
    return {"detail": "MFA diaktifkan"}
