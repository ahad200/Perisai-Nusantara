"""Uji RBAC & pemisahan tugas (PRD §3)."""
from __future__ import annotations

import pytest

from app.core.rbac import Permission, Role, has_permission, permissions_for
from tests.conftest import bearer, login


def _token(client, make_user, username, role):
    make_user(username, role, "Password123!")
    return login(client, username, "Password123!")["access_token"]


def test_platform_admin_can_create_user(client, make_user):
    tok = _token(client, make_user, "admin", Role.PLATFORM_ADMIN)
    r = client.post(
        "/users",
        headers=bearer(tok),
        json={"username": "baru", "full_name": "User Baru", "role": "analyst_t1", "password": "Password123!"},
    )
    assert r.status_code == 201
    assert r.json()["username"] == "baru"


def test_auditor_cannot_create_user(client, make_user):
    tok = _token(client, make_user, "aud", Role.AUDITOR)
    r = client.post(
        "/users",
        headers=bearer(tok),
        json={"username": "baru", "full_name": "x", "role": "analyst_t1", "password": "Password123!"},
    )
    assert r.status_code == 403


def test_analyst_cannot_read_audit(client, make_user):
    tok = _token(client, make_user, "t1", Role.ANALYST_T1)
    assert client.get("/audit", headers=bearer(tok)).status_code == 403
    assert client.get("/audit/verify", headers=bearer(tok)).status_code == 403


def test_auditor_can_read_and_verify_audit(client, make_user):
    tok = _token(client, make_user, "aud", Role.AUDITOR)
    assert client.get("/audit", headers=bearer(tok)).status_code == 200
    v = client.get("/audit/verify", headers=bearer(tok))
    assert v.status_code == 200
    assert v.json()["ok"] is True


def test_analyst_can_read_users(client, make_user):
    tok = _token(client, make_user, "t2", Role.ANALYST_T2)
    assert client.get("/users", headers=bearer(tok)).status_code == 200


# --- Pemisahan tugas pada level matriks izin (tanpa HTTP) --------------------

def test_no_role_can_mutate_audit():
    # Tidak ada permission mutasi audit sama sekali — audit immutable.
    mutate_like = {"audit:write", "audit:update", "audit:delete"}
    all_perms = {p.value for p in Permission}
    assert mutate_like.isdisjoint(all_perms)


def test_auditor_is_read_only():
    perms = permissions_for(Role.AUDITOR)
    assert Permission.USER_CREATE not in perms
    assert Permission.USER_MANAGE not in perms
    assert Permission.AUDIT_READ in perms


def test_platform_admin_manages_users_but_audit_read_only():
    assert has_permission(Role.PLATFORM_ADMIN, Permission.USER_MANAGE)
    # Tak punya izin mutasi audit karena izin itu tidak ada untuk siapa pun.
    assert has_permission(Role.PLATFORM_ADMIN, Permission.AUDIT_READ)


@pytest.mark.parametrize("role", list(Role))
def test_every_role_has_defined_permissions(role):
    # Setiap role terdaftar (boleh kosong, tapi harus ada di peta).
    assert isinstance(permissions_for(role), frozenset)
