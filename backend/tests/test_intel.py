"""Test threat intel: STIX import, siklus hidup, enrichment, RBAC (M4)."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.rbac import Role
from app.intel import expire_stale, import_bundle, lookup_enrichment, parse_pattern, set_status
from app.intel.samples import SAMPLE_BUNDLE, seed_intel
from app.models.ioc import IoC, IoCStatus, IoCType, Tlp, utcnow_naive

from tests.conftest import bearer, login


# --- Parser STIX ---

def test_parse_pattern_common_types():
    assert parse_pattern("[ipv4-addr:value = '1.2.3.4']") == [(IoCType.IP, "1.2.3.4")]
    assert parse_pattern("[domain-name:value = 'evil.com']") == [(IoCType.DOMAIN, "evil.com")]
    assert parse_pattern("[file:hashes.'SHA-256' = 'abc']") == [(IoCType.SHA256, "abc")]
    assert parse_pattern("[email-addr:value = 'a@b.id']") == [(IoCType.EMAIL, "a@b.id")]


def test_parse_pattern_unparseable_is_empty():
    assert parse_pattern("[x-custom:foo > 5]") == []


# --- Import bundle ---

def test_import_sample_bundle(db_session):
    res = seed_intel(db_session, record_audit=False)
    assert res["created"] == 5  # 5 indikator contoh
    assert res["mirror_rows"] > 0
    # Idempotent: impor ulang tidak membuat duplikat.
    res2 = import_bundle(db_session, SAMPLE_BUNDLE, record_audit=False)
    assert res2["created"] == 0 and res2["updated"] == 5


def test_import_sets_tlp_and_expiry(db_session):
    seed_intel(db_session, record_audit=False)
    c2 = db_session.execute(select(IoC).where(IoC.value == "198.51.100.23")).scalar_one()
    assert c2.tlp == Tlp.AMBER.value
    assert c2.effective_status() is IoCStatus.ACTIVE
    assert c2.is_blockable() is True
    # Indikator dengan valid_until lampau -> kedaluwarsa, tidak blockable.
    stale = db_session.execute(select(IoC).where(IoC.value == "192.0.2.50")).scalar_one()
    assert stale.effective_status() is IoCStatus.EXPIRED
    assert stale.is_blockable() is False


def test_import_invalid_bundle_raises(db_session):
    import pytest
    with pytest.raises(ValueError):
        import_bundle(db_session, {"type": "not-a-bundle"}, record_audit=False)


# --- Siklus hidup (FR-205) ---

def test_expire_stale_flips_active_to_expired(db_session):
    ioc = IoC(type="ip", value="10.0.0.9", source="t", tlp="AMBER", confidence=50,
              status=IoCStatus.ACTIVE.value, expires_at=utcnow_naive() - timedelta(days=1))
    db_session.add(ioc)
    db_session.commit()
    assert expire_stale(db_session, record_audit=False) == 1
    db_session.refresh(ioc)
    assert ioc.status == IoCStatus.EXPIRED.value


def test_whitelist_blocks_usage(db_session):
    seed_intel(db_session, record_audit=False)
    c2 = db_session.execute(select(IoC).where(IoC.value == "198.51.100.23")).scalar_one()
    set_status(db_session, c2, IoCStatus.WHITELISTED, actor_id="ti", record_audit=False)
    assert c2.effective_status() is IoCStatus.WHITELISTED
    assert c2.is_blockable() is False


# --- Enrichment mirror (FR-202) ---

def test_enrichment_lookup_local_only(db_session):
    seed_intel(db_session, record_audit=False)
    enr = lookup_enrichment(db_session, "198.51.100.23")
    kinds = {e["kind"] for e in enr}
    assert {"geoip", "whois", "reputation"} <= kinds
    assert all(e["mirror_age_days"] >= 0 for e in enr)  # usia data ditampilkan


# --- API + RBAC ---

def _token(client, make_user, username, role):
    make_user(username, role)
    return login(client, username, "Password123!")["access_token"]


def test_ti_officer_can_seed_and_list(client, make_user):
    tok = _token(client, make_user, "ti", Role.INTEL)
    r = client.post("/intel/seed", headers=bearer(tok))
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 5
    page = client.get("/intel/iocs", headers=bearer(tok)).json()
    assert page["total"] == 5


def test_ioc_detail_has_enrichment(client, make_user):
    tok = _token(client, make_user, "ti", Role.INTEL)
    client.post("/intel/seed", headers=bearer(tok))
    page = client.get("/intel/iocs?q=198.51.100.23", headers=bearer(tok)).json()
    ioc_id = page["items"][0]["id"]
    d = client.get(f"/intel/iocs/{ioc_id}", headers=bearer(tok)).json()
    assert len(d["enrichment"]) >= 2
    assert d["blockable"] is True


def test_analyst_can_read_but_not_manage(client, make_user):
    ti = _token(client, make_user, "ti", Role.INTEL)
    client.post("/intel/seed", headers=bearer(ti))
    a1 = _token(client, make_user, "a1", Role.OPERATOR)
    assert client.get("/intel/iocs", headers=bearer(a1)).status_code == 200
    assert client.post("/intel/seed", headers=bearer(a1)).status_code == 403
    assert client.post("/intel/iocs", headers=bearer(a1),
                       json={"type": "ip", "value": "9.9.9.9"}).status_code == 403


def test_status_filter(client, make_user):
    tok = _token(client, make_user, "ti", Role.INTEL)
    client.post("/intel/seed", headers=bearer(tok))
    expired = client.get("/intel/iocs?status=expired", headers=bearer(tok)).json()
    assert expired["total"] == 1  # 192.0.2.50
    assert all(i["status"] == "expired" for i in expired["items"])
