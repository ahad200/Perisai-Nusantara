"""Test SOAR: engine, Matriks Otonomi end-to-end, approval/timeout/eskalasi,
rollback, dry-run, RBAC (M8)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.rbac import Role
from app.models.asset import Asset, Criticality
from app.models.incident import Incident, IncidentStatus
from app.models.soar import (
    ActionExecution,
    ActionStatus,
    Approval,
    ApprovalStatus,
    PlaybookRun,
    RunMode,
    RunStatus,
)
from app.soar import process_timeouts, rollback_run, run_playbook, seed_playbooks
from app.soar.adapters import ACTION_LOG, reset_log

from tests.conftest import bearer, login


def _asset(db, hostname: str, crit: Criticality) -> Asset:
    a = Asset(hostname=hostname, ip="10.0.0.1", segment="seg", owner="o", criticality=crit.value, tags=[])
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


_SEQ = [0]


def _incident(db, *, severity: str, crit: Criticality, technique: str, host: str) -> Incident:
    _SEQ[0] += 1
    n = _SEQ[0]
    a = _asset(db, host, crit)
    inc = Incident(
        incident_code=f"INC-T{n:05d}", correlation_key=f"host:{host}:{n}",
        title=f"Insiden {host}", summary="", severity=severity,
        status=IncidentStatus.OPEN.value, asset_id=a.id, host=host,
        techniques=[{"technique": technique, "name": technique}], alert_count=1,
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


def _actions(db, run_id):
    return db.execute(
        select(ActionExecution).where(ActionExecution.run_id == run_id)
        .order_by(ActionExecution.step_index)
    ).scalars().all()


# --- Acceptance: ransomware K3 auto, K1 approval Commander ---

def test_ransomware_k3_auto_isolate(db_session):
    seed_playbooks(db_session)
    reset_log()
    inc = _incident(db_session, severity="critical", crit=Criticality.K3, technique="T1486", host="ws-k3")
    run = run_playbook(db_session, incident_id=inc.id, actor="responder")
    assert run.status == RunStatus.COMPLETED.value
    acts = _actions(db_session, run.id)
    isolate = next(a for a in acts if a.action == "isolate_host")
    assert isolate.status == ActionStatus.EXECUTED.value
    assert isolate.decision_mode == "auto"
    # Adapter mock benar-benar "mengeksekusi" (mencatat).
    assert any(e["op"] == "execute" and e["action"] == "isolate_host" for e in ACTION_LOG)


def test_ransomware_k1_awaits_commander(db_session):
    seed_playbooks(db_session)
    inc = _incident(db_session, severity="critical", crit=Criticality.K1, technique="T1486", host="dc-k1")
    run = run_playbook(db_session, incident_id=inc.id, actor="responder")
    assert run.status == RunStatus.AWAITING_APPROVAL.value
    isolate = next(a for a in _actions(db_session, run.id) if a.action == "isolate_host")
    assert isolate.status == ActionStatus.AWAITING_APPROVAL.value
    ap = db_session.get(Approval, isolate.approval_id)
    assert ap.status == ApprovalStatus.PENDING.value
    assert ap.required_tier == "commander"


def test_rollback_reverses_executed_actions(db_session):
    seed_playbooks(db_session)
    reset_log()
    inc = _incident(db_session, severity="critical", crit=Criticality.K3, technique="T1486", host="ws-rb")
    run = run_playbook(db_session, incident_id=inc.id, actor="responder")
    res = rollback_run(db_session, run_id=run.id, actor="responder")
    assert res["rolled_back"] >= 1
    isolate = next(a for a in _actions(db_session, run.id) if a.action == "isolate_host")
    assert isolate.rolled_back is True and isolate.status == ActionStatus.ROLLED_BACK.value
    assert any(e["op"] == "rollback" and e["action"] == "isolate_host" for e in ACTION_LOG)
    # Aksi tak reversibel (collect_forensics) tidak di-rollback.
    forensic = next(a for a in _actions(db_session, run.id) if a.action == "collect_forensics")
    assert forensic.rolled_back is False


def test_dry_run_has_no_effect(db_session):
    seed_playbooks(db_session)
    reset_log()
    inc = _incident(db_session, severity="critical", crit=Criticality.K1, technique="T1486", host="dc-dry")
    run = run_playbook(db_session, incident_id=inc.id, mode=RunMode.DRY_RUN.value, actor="responder")
    assert run.status == RunStatus.COMPLETED.value
    assert all(a.status == ActionStatus.SIMULATED.value for a in _actions(db_session, run.id))
    # Tidak ada efek: adapter tak dipanggil, tak ada approval.
    assert ACTION_LOG == []
    assert db_session.execute(select(Approval)).scalars().all() == []


# --- Timeout & eskalasi (§7 no.2) ---

def test_high_k2_timeout_executes_auto(db_session):
    seed_playbooks(db_session)
    inc = _incident(db_session, severity="high", crit=Criticality.K2, technique="T1110", host="app-k2")
    run = run_playbook(db_session, incident_id=inc.id, actor="responder")
    assert run.status == RunStatus.AWAITING_APPROVAL.value
    future = datetime.now(timezone.utc) + timedelta(minutes=20)
    res = process_timeouts(db_session, now=future, actor="system")
    assert res["auto"] >= 1
    aps = db_session.execute(select(Approval)).scalars().all()
    assert all(a.status == ApprovalStatus.AUTO_TIMEOUT.value for a in aps)
    assert all(a.status == ActionStatus.EXECUTED.value for a in _actions(db_session, run.id))


def test_approval_escalates_to_next_tier(db_session):
    seed_playbooks(db_session)
    # medium × K1 → approval tier analyst_t2, on_timeout escalate.
    inc = _incident(db_session, severity="medium", crit=Criticality.K1, technique="T1036", host="dc-esc")
    run = run_playbook(db_session, incident_id=inc.id, actor="responder")
    ap = db_session.execute(
        select(Approval).where(Approval.status == ApprovalStatus.PENDING.value)
    ).scalars().first()
    assert ap.required_tier == "analyst_t2"
    # Beri deadline lampau untuk memicu eskalasi.
    ap.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    res = process_timeouts(db_session, actor="system")
    assert res["escalated"] == 1
    db_session.refresh(ap)
    assert ap.required_tier == "analyst_t3" and ap.status == ApprovalStatus.PENDING.value


# --- API + RBAC ---

def _token(client, make_user, username, role):
    make_user(username, role)
    return login(client, username, "Password123!")["access_token"]


def test_responder_runs_and_commander_approves(client, make_user, db_session):
    seed_playbooks(db_session)
    inc = _incident(db_session, severity="critical", crit=Criticality.K1, technique="T1486", host="dc-api")

    resp = _token(client, make_user, "resp", Role.RESPONDER)
    r = client.post("/soar/run", headers=bearer(resp), json={"incident_id": inc.id})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "awaiting_approval"
    ap_id = next(a["approval_id"] for a in run["actions"] if a["action"] == "isolate_host")

    # T2 tak boleh menyetujui approval tier commander.
    t2 = _token(client, make_user, "t2", Role.ANALYST_T2)
    low = client.post(f"/soar/approvals/{ap_id}/resolve", headers=bearer(t2), json={"decision": "approve"})
    assert low.status_code == 403

    # Commander menyetujui → aksi dieksekusi.
    cmd = _token(client, make_user, "cmd", Role.COMMANDER)
    ok = client.post(f"/soar/approvals/{ap_id}/resolve", headers=bearer(cmd), json={"decision": "approve"})
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    detail = client.get(f"/soar/runs/{run['id']}", headers=bearer(resp)).json()
    isolate = next(a for a in detail["actions"] if a["action"] == "isolate_host")
    assert isolate["status"] == "executed"


def test_soar_rbac(client, make_user, db_session):
    seed_playbooks(db_session)
    inc = _incident(db_session, severity="low", crit=Criticality.K3, technique="T1486", host="ws-rbac")
    # Analis T1 tak boleh menjalankan playbook.
    t1 = _token(client, make_user, "t1b", Role.ANALYST_T1)
    assert client.post("/soar/run", headers=bearer(t1), json={"incident_id": inc.id}).status_code == 403
    # Tapi boleh melihat playbook (soar:read).
    assert client.get("/soar/playbooks", headers=bearer(t1)).status_code == 200
    # Auditor read-only: tak boleh approve.
    aud = _token(client, make_user, "aud2", Role.AUDITOR)
    assert client.post("/soar/approvals/1/resolve", headers=bearer(aud), json={"decision": "approve"}).status_code == 403


def test_break_glass_auto_executes_non_k1(client, make_user, db_session):
    seed_playbooks(db_session)
    # medium × K1 biasanya approval; tapi K1 tetap approval walau break-glass.
    inc_k2 = _incident(db_session, severity="high", crit=Criticality.K2, technique="T1110", host="app-bg")
    cmd = _token(client, make_user, "cmd2", Role.COMMANDER)
    # Aktifkan break-glass (commander, soar:manage).
    bg = client.post("/soar/break-glass", headers=bearer(cmd), json={"reason": "latihan", "minutes": 30})
    assert bg.status_code == 200
    resp = _token(client, make_user, "resp2", Role.RESPONDER)
    run = client.post("/soar/run", headers=bearer(resp), json={"incident_id": inc_k2.id}).json()
    # Break-glass → high×K2 (biasanya approval) jadi auto.
    assert run["status"] == "completed"
    assert all(a["status"] == "executed" for a in run["actions"])
