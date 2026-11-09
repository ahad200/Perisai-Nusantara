"""Uji autentikasi: login, JWT, dan alur MFA (TOTP)."""
from __future__ import annotations

import pyotp

from app.core.rbac import Role
from tests.conftest import bearer, login


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_success_no_mfa(client, make_user):
    make_user("cmd", Role.COMMANDER, "Password123!")
    res = login(client, "cmd", "Password123!")
    assert res["_status"] == 200
    assert res["mfa_required"] is False
    assert res["access_token"]

    me = client.get("/auth/me", headers=bearer(res["access_token"]))
    assert me.status_code == 200
    assert me.json()["username"] == "cmd"
    assert me.json()["role"] == "commander"


def test_login_wrong_password(client, make_user):
    make_user("cmd", Role.COMMANDER, "Password123!")
    res = login(client, "cmd", "salah")
    assert res["_status"] == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code in (401, 403)


def test_mfa_setup_enable_and_two_step_login(client, make_user):
    make_user("analis", Role.OPERATOR, "Password123!")
    # Login awal tanpa MFA.
    res = login(client, "analis", "Password123!")
    token = res["access_token"]

    # Setup MFA -> dapat secret.
    setup = client.post("/auth/mfa/setup", headers=bearer(token))
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["otpauth_uri"].startswith("otpauth://")

    totp = pyotp.TOTP(secret)
    # Enable dengan OTP valid.
    en = client.post("/auth/mfa/enable", headers=bearer(token), json={"otp_code": totp.now()})
    assert en.status_code == 200

    # Sekarang login tanpa OTP -> tantangan MFA.
    challenge = login(client, "analis", "Password123!")
    assert challenge["_status"] == 200
    assert challenge["mfa_required"] is True
    assert challenge["mfa_token"]
    assert challenge["access_token"] is None

    # Selesaikan MFA.
    done = client.post(
        "/auth/mfa", json={"mfa_token": challenge["mfa_token"], "otp_code": totp.now()}
    )
    assert done.status_code == 200
    assert done.json()["access_token"]


def test_mfa_wrong_otp_rejected(client, make_user):
    secret = pyotp.random_base32()
    make_user("x", Role.OPERATOR, "Password123!", mfa_enabled=True, totp_secret=secret)
    res = login(client, "x", "Password123!", otp_code="000000")
    assert res["_status"] == 401
