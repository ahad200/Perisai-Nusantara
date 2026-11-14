"""Test simulator: fleet, baseline >=14 hari, skenario serangan, audit (M3)."""
from __future__ import annotations

from app import audit
from app.core.rbac import Role
from app.models.event import Event
from app.simulator import (
    FLEET,
    generate_baseline,
    scenario_beaconing,
    scenario_bruteforce,
    scenario_ransomware,
    seed_assets,
)

from tests.conftest import bearer, login


def test_seed_assets_creates_fleet(db_session):
    created = seed_assets(db_session, record_audit=False)
    assert len(created) == len(FLEET)
    # Idempotent: jalan kedua tidak membuat aset baru.
    assert seed_assets(db_session, record_audit=False) == []


def test_baseline_spans_at_least_14_days(db_session):
    seed_assets(db_session, record_audit=False)
    n = generate_baseline(db_session, days=14, seed=7, record_audit=False)
    assert n > 0
    dates = {t.date() for (t,) in db_session.query(Event.ts).filter(Event.scenario == "baseline").all()}
    assert len(dates) >= 14, f"baseline hanya mencakup {len(dates)} hari"
    assert all(e.scenario == "baseline" for e in db_session.query(Event).filter(Event.scenario == "baseline").limit(5))


def test_bruteforce_pattern_t1110(db_session):
    seed_assets(db_session, record_audit=False)
    res = scenario_bruteforce(db_session, attempts=50, record_audit=False)
    assert res.technique == "T1110"
    events = db_session.query(Event).filter(Event.scenario == "bruteforce").all()
    failures = [e for e in events if e.outcome == "failure"]
    assert len(failures) >= 50
    # Semua dari satu sumber & satu host target (ciri brute force).
    assert {e.src_ip for e in failures} == {"203.0.113.66"}
    assert {e.host for e in events} == {res.target}


def test_beaconing_pattern_t1071(db_session):
    seed_assets(db_session, record_audit=False)
    res = scenario_beaconing(db_session, duration_hours=2, interval_seconds=60, record_audit=False)
    assert res.technique == "T1071"
    events = db_session.query(Event).filter(Event.scenario == "beaconing").order_by(Event.ts).all()
    assert len(events) >= 100  # ~2 jam / 60 dtk
    # Tujuan tunggal (C2) — ciri beaconing.
    assert {e.dst_ip for e in events} == {"198.51.100.23"}


def test_ransomware_pattern_t1486(db_session):
    seed_assets(db_session, record_audit=False)
    res = scenario_ransomware(db_session, bursts=30, record_audit=False)
    assert res.technique == "T1486"
    events = db_session.query(Event).filter(Event.scenario == "ransomware").all()
    file_events = [e for e in events if e.category == "file"]
    assert len(file_events) >= 30  # ledakan modifikasi berkas
    assert any(e.category == "process" for e in events)  # proses mencurigakan


def test_simulator_keeps_audit_chain_intact(db_session):
    seed_assets(db_session)  # menulis audit
    scenario_bruteforce(db_session, attempts=10)  # menulis audit batch
    result = audit.verify_chain(db_session)
    assert result["ok"] is True


# --- Endpoint /dev/simulate (demo UI) ---

def _token(client, make_user, username, role):
    make_user(username, role)
    return login(client, username, "Password123!")["access_token"]


def test_purple_team_can_trigger_simulation(client, make_user):
    tok = _token(client, make_user, "purple", Role.OPERATOR)
    r = client.post("/dev/simulate", headers=bearer(tok), json={"scenario": "bruteforce"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ran"] == "bruteforce"
    assert body["results"][0]["count"] > 0
    # Event benar-benar masuk & bisa difilter.
    ev = client.get("/events?scenario=bruteforce", headers=bearer(tok)).json()
    assert ev["total"] > 0


def test_non_operator_cannot_trigger_simulation(client, make_user):
    # Auditor read-only tak punya sim:run → tak boleh memicu simulasi.
    tok = _token(client, make_user, "aud", Role.AUDITOR)
    r = client.post("/dev/simulate", headers=bearer(tok), json={"scenario": "bruteforce"})
    assert r.status_code == 403


# --- Target skenario (demo bertahap & serentak) ---

def test_scenario_rejects_unknown_target(db_session):
    import pytest
    seed_assets(db_session, record_audit=False)
    with pytest.raises(ValueError, match="Target tak dikenal"):
        scenario_ransomware(db_session, target="tidak-ada-01", record_audit=False)


def test_simulate_ransomware_on_multiple_targets(client, make_user):
    tok = _token(client, make_user, "op", Role.OPERATOR)
    r = client.post("/dev/simulate", headers=bearer(tok), json={
        "scenario": "ransomware", "targets": ["ws-staff-05", "cmd-core-01"],
    })
    assert r.status_code == 200, r.text
    targets = [i["target"] for i in r.json()["results"]]
    assert targets == ["ws-staff-05", "cmd-core-01"]
    ev = client.get("/events?scenario=ransomware&host=cmd-core-01", headers=bearer(tok)).json()
    assert ev["total"] > 0


def test_simulate_rejects_bad_targets(client, make_user):
    tok = _token(client, make_user, "op", Role.OPERATOR)
    r = client.post("/dev/simulate", headers=bearer(tok),
                    json={"scenario": "bruteforce", "targets": ["tidak-ada-01"]})
    assert r.status_code == 400
    r = client.post("/dev/simulate", headers=bearer(tok),
                    json={"scenario": "all", "targets": ["ws-staff-05"]})
    assert r.status_code == 400
