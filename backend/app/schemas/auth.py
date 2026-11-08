"""Skema autentikasi & MFA."""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str
    otp_code: str | None = Field(
        default=None, description="Kode TOTP 6 digit (bila MFA aktif, boleh dikirim langsung)"
    )


class LoginResponse(BaseModel):
    """Hasil login. Bila MFA aktif & OTP belum diberikan, kembalikan tantangan."""

    mfa_required: bool = False
    access_token: str | None = None
    token_type: str | None = None
    mfa_token: str | None = Field(
        default=None, description="Token sementara untuk menyelesaikan MFA via /auth/mfa"
    )


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    otp_code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MfaSetupResponse(BaseModel):
    secret: str = Field(description="Secret TOTP (base32). Tampil sekali, simpan aman.")
    otpauth_uri: str = Field(description="URI otpauth:// untuk dipindai authenticator.")


class MfaEnableRequest(BaseModel):
    otp_code: str
