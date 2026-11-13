"""Test alur investigasi OODA (read-only) + peta segmen per host di Situasi."""
from __future__ import annotations

from sqlalchemy import select

from app.agents.service import run_attribution
from app.core.rbac import Role
from app.correlation import correlate
from app.correlation.ooda import build_ooda
from app.detection import run_detection, seed_rules
from app.intel.samples import seed_intel
from app.models.asset import Asset, Criticality
from app.models.audit import AuditEntry
from app.models.incident import Incident, IncidentStatus
from app.reports import metrics
from app.simulator import run_all_scenarios, seed_assets
from app.soar import run_playbook, seed_playbooks
from app.soar.adapters import ACTION_LOG, reset_log

from tests.conftest import bearer, login


def _prepare(db):
    seed_assets(db, record_audit=False)
    run_all_scenarios(db, record_audit=False)
    seed_intel(db, record_audit=False)
    seed_rules(db)
    run_detection(db, record_audit=False)
    correlate(db, record_audit=False)


def _incident_on(db, crit: str) -> Incident:
    return db.execute(
        select(Incident).join(Asset, Incident.asset_id == Asset.id)
        .where(Asset.criticality == crit).order_by(Incident.id)
    ).scalars().first()


def _phase(o, key):
    return next(p for p in o["phases"] if p["key"] == key)


def test_fresh_incident_observed_but_not_decided(db_session):
    _prepare(db_session)
    inc = db_session.execute(select(Incident).order_by(Incident.id)).scalars().first()
    o = build_ooda(db_session, inc)
    assert [p["key"] for p in o["phases"]] == ["observe", "orient", "decide", "act"]
    obs = _phase(o, "observe")
    assert obs["state"] == "recorded"
    assert all(it["ref"].startswith("ALERT-") for it in obs["items"])
    # Belum ada playbook → fase Decide yang jadi fase berjalan.
    assert _phase(o, "decide")["state"] == "empty"
    assert o["current_phase"] == "decide"


def test_k1_playbook_waits_on_commander(db_session):
    seed_playbooks(db_session)
    a = Asset(hostname="cmd-x", ip="10.10.1.99", segment="komando", owner="o",
              criticality=Criticality.K1.value, tags=[])
    db_session.add(a)
    db_session.commit()
    inc = Incident(incident_code="INC-K1-1", correlation_key="host:cmd-x", title="t",
                   summary="", severity="critical", status=IncidentStatus.OPEN.value,
                   asset_id=a.id, host="cmd-x",
                   techniques=[{"technique": "T1486", "name": "Data Encrypted for Impact"}],
                   alert_count=1)
    db_session.add(inc)
    db_session.commit()
    run_playbook(db_session, incident_id=inc.id, actor="operator", record_audit=False)
    o = build_ooda(db_session, inc)
    decide = _phase(o, "decide")
    assert decide["state"] == "waiting"
    assert "approval" in decide["waiting_reason"]
    assert any(it["kind"] == "approval" for it in decide["items"])
    # Aksi disruptif K1 ditahan → Act juga menandai "waiting".
    assert _phase(o, "act")["state"] == "waiting"


def test_k3_auto_actions_land_in_act(db_session):
    _prepare(db_session)
    seed_playbooks(db_session)
    inc = _incident_on(db_session, "K3")
    run_playbook(db_session, incident_id=inc.id, actor="operator", record_audit=False)
    act = _phase(build_ooda(db_session, inc), "act")
    assert any(it["kind"] == "action" for it in act["items"])


def test_unvalidated_attribution_marks_orient_waiting(db_session):
    _prepare(db_session)
    inc = db_session.execute(select(Incident).order_by(Incident.id)).scalars().first()
    run_attribution(db_session, incident_id=inc.id)
    orient = _phase(build_ooda(db_session, inc), "orient")
    assert orient["state"] == "waiting"
    assert any(it["kind"] == "attribution" for it in orient["items"])


def test_missing_criticality_is_failsafe_k1(db_session):
    a = Asset(hostname="tanpa-krit", ip="10.9.9.9", segment="x", owner="o", criticality="", tags=[])
    db_session.add(a)
    db_session.commit()
    inc = Incident(incident_code="INC-FS-1", correlation_key="host:tanpa-krit", title="t",
                   summary="", severity="high", status=IncidentStatus.OPEN.value,
                   asset_id=a.id, host="tanpa-krit", techniques=[], alert_count=0)
    db_session.add(inc)
    db_session.commit()
    o = build_ooda(db_session, inc)
    assert o["criticality"] == "K1"
    assert o["current_phase"] == "observe"  # tanpa alert


def test_closed_incident_phase(db_session):
    _prepare(db_session)
    inc = db_session.execute(select(Incident).order_by(Incident.id)).scalars().first()
    inc.status = IncidentStatus.CLOSED.value
    db_session.commit()
    assert build_ooda(db_session, inc)["current_phase"] == "closed"


def test_ooda_is_read_only(db_session):
    """Membangun OODA tak menulis audit & tak menyentuh adapter (§A.5 no.1)."""
    _prepare(db_session)
    inc = db_session.execute(select(Incident).order_by(Incident.id)).scalars().first()
    reset_log()
    before = db_session.execute(select(AuditEntry.id)).all()
    build_ooda(db_session, inc)
    assert db_session.execute(select(AuditEntry.id)).all() == before
    assert ACTION_LOG == []


def test_ooda_api_all_roles_read(client, make_user, db_session):
    _prepare(db_session)
    inc = db_session.execute(select(Incident).order_by(Incident.id)).scalars().first()
    for i, role in enumerate(Role):
        make_user(f"u{i}", role)
        tok = login(client, f"u{i}", "Password123!")["access_token"]
        r = client.get(f"/incidents/{inc.id}/ooda", headers=bearer(tok))
        assert r.status_code == 200, role
        assert r.json()["incident_code"] == inc.incident_code
    assert client.get("/incidents/99999/ooda", headers=bearer(tok)).status_code == 404
    assert client.get(f"/incidents/{inc.id}/ooda").status_code == 401


# --- Peta segmen per host (Situasi) --------------------------------------- #
def test_segment_map_hosts_and_order(db_session):
    _prepare(db_session)
    segs = metrics.situasi_snapshot(db_session)["segments"]
    # Diurutkan dari kritikalitas tertinggi.
    ranks = [{"K1": 3, "K2": 2, "K3": 1}[s["max_criticality"]] for s in segs]
    assert ranks == sorted(ranks, reverse=True)
    for s in segs:
        assert len(s["hosts"]) == s["assets"]
        assert s["active_incidents"] == sum(h["active_incidents"] for h in s["hosts"])
    hosts = [h for s in segs for h in s["hosts"]]
    hit = [h for h in hosts if h["active_incidents"]]
    assert hit and all(h["incident_id"] and h["max_severity"] for h in hit)


def test_segment_map_failsafe_criticality(db_session):
    db_session.add(Asset(hostname="h-kosong", ip="10.1.1.1", segment="lab", owner="o",
                         criticality="", tags=[]))
    db_session.add(Asset(hostname="h-k3", ip="10.1.1.2", segment="lab", owner="o",
                         criticality=Criticality.K3.value, tags=[]))
    db_session.commit()
    seg = next(s for s in metrics.situasi_snapshot(db_session)["segments"] if s["segment"] == "lab")
    assert seg["K1"] == 1 and seg["max_criticality"] == "K1"
