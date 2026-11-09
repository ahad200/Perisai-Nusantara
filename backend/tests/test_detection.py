"""Test deteksi: matcher, mesin, antrian alert + RBAC (M5)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.rbac import Role
from app.detection import run_detection, seed_rules
from app.detection.matcher import densest_window, sigma_match
from app.intel.samples import seed_intel
from app.models.alert import Alert, AlertStatus
from app.models.event import Event
from app.models.ioc import IoC, IoCStatus
from app.simulator import run_all_scenarios, seed_assets

from tests.conftest import bearer, login


# --- Matcher unit ---

def test_sigma_match_scalar_and_list_and_raw():
    e = Event(source_type="edr", action="process_start", host="h", category="process",
              outcome="success", message="", raw={"process": "svch0st.exe"})
    assert sigma_match({"source_type": "edr", "raw.process": ["svch0st.exe", "x"]}, e) is True
    assert sigma_match({"raw.process": "notepad.exe"}, e) is False
    assert sigma_match({"message|contains": ""}, e) is True


def test_densest_window():
    base = datetime(2026, 11, 1, 0, 0)
    ts = [base + timedelta(seconds=s) for s in (0, 1, 2, 3, 1000)]
    assert densest_window(ts, 60, 4) == (0, 3)
    assert densest_window(ts, 60, 6) is None


# --- Engine ---

def _prepare(db):
    seed_assets(db, record_audit=False)
    run_all_scenarios(db, record_audit=False)
    seed_intel(db, record_audit=False)
    seed_rules(db)


def test_detection_produces_attack_alerts(db_session):
    _prepare(db_session)
    res = run_detection(db_session, record_audit=False)
    assert res["created"] >= 4
    techniques = {a.technique for a in db_session.execute(select(Alert)).scalars().all()}
    # Ketiga skenario + proses mencurigakan terpetakan ke ATT&CK.
    assert {"T1110", "T1486", "T1036", "T1071"} <= techniques


def test_bruteforce_alert_links_events(db_session):
    _prepare(db_session)
    run_detection(db_session, record_audit=False)
    bf = db_session.execute(
        select(Alert).where(Alert.rule_code == "PNX-BF-001")
    ).scalars().all()
    assert len(bf) == 1
    alert = bf[0]
    assert alert.severity == "high" and alert.technique == "T1110"
    assert alert.event_count >= 10
    assert alert.host == "app-logistik-01"


def test_detection_idempotent(db_session):
    _prepare(db_session)
    first = run_detection(db_session, record_audit=False)
    second = run_detection(db_session, record_audit=False)
    assert second["created"] == 0
    assert second["updated"] >= first["created"]


def test_ioc_match_respects_whitelist(db_session):
    seed_assets(db_session, record_audit=False)
    run_all_scenarios(db_session, record_audit=False)
    seed_intel(db_session, record_audit=False)
    seed_rules(db_session)
    # Whitelist IoC C2 -> tidak boleh menghasilkan alert IoC untuknya.
    c2 = db_session.execute(select(IoC).where(IoC.value == "198.51.100.23")).scalar_one()
    c2.status = IoCStatus.WHITELISTED.value
    db_session.commit()
    run_detection(db_session, record_audit=False)
    ioc_alerts = db_session.execute(
        select(Alert).where(Alert.dedup_key.like(f"ioc:{c2.id}:%"))
    ).scalars().all()
    assert ioc_alerts == []


# --- API + RBAC ---

def _token(client, make_user, username, role):
    make_user(username, role)
    return login(client, username, "Password123!")["access_token"]


def _seed_via_api(client, db_session):
    # Siapkan data (assets+events+intel) langsung di DB, lalu deteksi via API.
    seed_assets(db_session, record_audit=False)
    run_all_scenarios(db_session, record_audit=False)
    seed_intel(db_session, record_audit=False)


def test_analyst_runs_detection_and_triages(client, make_user, db_session):
    _seed_via_api(client, db_session)
    tok = _token(client, make_user, "a1", Role.OPERATOR)
    r = client.post("/detection/run", headers=bearer(tok))
    assert r.status_code == 200, r.text
    assert r.json()["created"] >= 4

    page = client.get("/alerts", headers=bearer(tok)).json()
    assert page["total"] >= 4
    # Antrian terurut: severity tertinggi (critical) di atas.
    assert page["items"][0]["severity"] in ("critical", "high")

    aid = page["items"][0]["id"]
    assigned = client.post(f"/alerts/{aid}/assign", headers=bearer(tok), json={}).json()
    assert assigned["assignee"] == "a1" and assigned["status"] == "assigned"
    esc = client.post(f"/alerts/{aid}/escalate", headers=bearer(tok)).json()
    assert esc["status"] == "escalated"
    closed = client.post(f"/alerts/{aid}/close", headers=bearer(tok), json={"reason": "fp"}).json()
    assert closed["status"] == "closed_fp"


def test_auditor_cannot_run_or_triage(client, make_user, db_session):
    _seed_via_api(client, db_session)
    a1 = _token(client, make_user, "a1", Role.OPERATOR)
    client.post("/detection/run", headers=bearer(a1))
    aid = client.get("/alerts", headers=bearer(a1)).json()["items"][0]["id"]

    aud = _token(client, make_user, "aud", Role.AUDITOR)
    assert client.get("/alerts", headers=bearer(aud)).status_code == 200  # boleh baca
    assert client.post("/detection/run", headers=bearer(aud)).status_code == 403
    assert client.post(f"/alerts/{aid}/assign", headers=bearer(aud), json={}).status_code == 403


def test_alert_detail_has_events(client, make_user, db_session):
    _seed_via_api(client, db_session)
    tok = _token(client, make_user, "a1", Role.OPERATOR)
    client.post("/detection/run", headers=bearer(tok))
    aid = client.get("/alerts?technique=T1110", headers=bearer(tok)).json()["items"][0]["id"]
    d = client.get(f"/alerts/{aid}", headers=bearer(tok)).json()
    assert len(d["events"]) >= 1 and len(d["event_ids"]) >= 10
