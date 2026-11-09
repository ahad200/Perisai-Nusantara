"""Test inventaris aset + RBAC (M3, FR-702)."""
from __future__ import annotations

from app.core.rbac import Role
from app.models.asset import Criticality, resolve_criticality

from tests.conftest import bearer, login


def _token(client, make_user, username, role):
    make_user(username, role)
    return login(client, username, "Password123!")["access_token"]


def test_resolve_criticality_failsafe():
    assert resolve_criticality(None) is Criticality.K1
    assert resolve_criticality("") is Criticality.K1
    assert resolve_criticality("ngawur") is Criticality.K1
    assert resolve_criticality("k2") is Criticality.K2
    assert resolve_criticality(Criticality.K3) is Criticality.K3


def test_admin_can_create_and_list_asset(client, make_user):
    tok = _token(client, make_user, "admin", Role.COMMANDER)
    r = client.post("/assets", headers=bearer(tok), json={
        "hostname": "srv-01", "ip": "10.0.0.5", "segment": "inti",
        "owner": "Pusdatin", "criticality": "K1", "tags": ["server"],
    })
    assert r.status_code == 201, r.text
    assert r.json()["criticality"] == "K1"

    r2 = client.get("/assets", headers=bearer(tok))
    assert r2.status_code == 200
    assert any(a["hostname"] == "srv-01" for a in r2.json())


def test_create_without_criticality_defaults_k1(client, make_user):
    tok = _token(client, make_user, "admin", Role.COMMANDER)
    r = client.post("/assets", headers=bearer(tok), json={"hostname": "srv-nc"})
    assert r.status_code == 201
    assert r.json()["criticality"] == "K1"  # fail-safe


def test_auditor_cannot_create_asset(client, make_user):
    tok = _token(client, make_user, "auditor", Role.AUDITOR)
    r = client.post("/assets", headers=bearer(tok), json={"hostname": "srv-x"})
    assert r.status_code == 403  # read-only, pemisahan tugas


def test_analyst_can_read_but_not_manage(client, make_user):
    tok = _token(client, make_user, "a1", Role.OPERATOR)
    assert client.get("/assets", headers=bearer(tok)).status_code == 200
    assert client.post("/assets", headers=bearer(tok), json={"hostname": "z"}).status_code == 403


def test_filter_by_criticality(client, make_user):
    tok = _token(client, make_user, "admin", Role.COMMANDER)
    client.post("/assets", headers=bearer(tok), json={"hostname": "k1a", "criticality": "K1"})
    client.post("/assets", headers=bearer(tok), json={"hostname": "k3a", "criticality": "K3"})
    r = client.get("/assets?criticality=K3", headers=bearer(tok))
    hosts = [a["hostname"] for a in r.json()]
    assert "k3a" in hosts and "k1a" not in hosts


def test_duplicate_hostname_conflict(client, make_user):
    tok = _token(client, make_user, "admin", Role.COMMANDER)
    client.post("/assets", headers=bearer(tok), json={"hostname": "dup"})
    r = client.post("/assets", headers=bearer(tok), json={"hostname": "dup"})
    assert r.status_code == 409
