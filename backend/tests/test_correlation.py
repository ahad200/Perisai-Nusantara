"""Test korelasi alert -> insiden + case management (M7)."""
from __future__ import annotations

from sqlalchemy import select

from app.core.rbac import Role
from app.correlation import correlate
from app.detection import run_detection, seed_rules
from app.intel.samples import seed_intel
from app.models.alert import Alert, AlertStatus
from app.models.incident import Incident, IncidentNote, IncidentStatus
from app.simulator import run_all_scenarios, seed_assets

from tests.conftest import bearer, login


def _prepare(db):
    seed_assets(db, record_audit=False)
    run_all_scenarios(db, record_audit=False)
    seed_intel(db, record_audit=False)
    seed_rules(db)
    run_detection(db, record_audit=False)


# --- Mesin korelasi (unit) ---

def test_correlation_groups_alerts_into_incidents(db_session):
    _prepare(db_session)
    res = correlate(db_session, record_audit=False)
    assert res["created"] >= 1
    incidents = db_session.execute(select(Incident)).scalars().all()
    assert incidents
    # Setiap insiden punya kode, severity = severity tertinggi anggotanya.
    for inc in incidents:
        assert inc.incident_code.startswith("INC-")
        members = db_session.execute(
            select(Alert).where(Alert.incident_id == inc.id)
        ).scalars().all()
        assert members
        assert inc.alert_count == len(members)
        assert inc.severity in {a.severity for a in members}


def test_incident_aggregates_attack_techniques(db_session):
    _prepare(db_session)
    correlate(db_session, record_audit=False)
    # Host brute force app-logistik-01 harus punya insiden dengan teknik T1110.
    inc = db_session.execute(
        select(Incident).where(Incident.host == "app-logistik-01")
    ).scalar_one()
    techs = {t["technique"] for t in inc.techniques}
    assert "T1110" in techs


def test_correlation_idempotent(db_session):
    _prepare(db_session)
    first = correlate(db_session, record_audit=False)
    second = correlate(db_session, record_audit=False)
    assert second["created"] == 0
    assert second["incidents"] == first["incidents"]
    # Tidak ada duplikasi insiden.
    keys = [i.correlation_key for i in db_session.execute(select(Incident)).scalars().all()]
    assert len(keys) == len(set(keys))


def test_fp_alert_excluded_from_new_incident(db_session):
    _prepare(db_session)
    # Tutup semua alert pada satu host sebagai FP sebelum korelasi.
    bf = db_session.execute(
        select(Alert).where(Alert.host == "app-logistik-01")
    ).scalars().all()
    for a in bf:
        a.status = AlertStatus.CLOSED_FP.value
    db_session.commit()
    correlate(db_session, record_audit=False)
    inc = db_session.execute(
        select(Incident).where(Incident.host == "app-logistik-01")
    ).scalar_one_or_none()
    assert inc is None  # tak ada alert aktif -> tak ada insiden


# --- API + case management ---

def _token(client, make_user, username, role):
    make_user(username, role)
    return login(client, username, "Password123!")["access_token"]


def _seed_and_correlate(client, db_session, tok):
    seed_assets(db_session, record_audit=False)
    run_all_scenarios(db_session, record_audit=False)
    seed_intel(db_session, record_audit=False)
    client.post("/detection/run", headers=bearer(tok))


def test_responder_runs_correlation_and_manages_case(client, make_user, db_session):
    a3 = _token(client, make_user, "a3", Role.ANALYST_T3)  # bisa run detection
    _seed_and_correlate(client, db_session, a3)
    resp = _token(client, make_user, "resp", Role.RESPONDER)

    r = client.post("/incidents/correlate", headers=bearer(resp))
    assert r.status_code == 200, r.text
    assert r.json()["created"] >= 1

    page = client.get("/incidents", headers=bearer(resp)).json()
    assert page["total"] >= 1
    iid = page["items"][0]["id"]

    # Assign
    assigned = client.post(f"/incidents/{iid}/assign", headers=bearer(resp), json={}).json()
    assert assigned["assignee"] == "resp"

    # Ubah status siklus hidup + catatan.
    st = client.post(f"/incidents/{iid}/status", headers=bearer(resp),
                     json={"status": "contained", "note": "Aset diisolasi."}).json()
    assert st["status"] == IncidentStatus.CONTAINED.value

    # Tambah catatan kasus.
    note = client.post(f"/incidents/{iid}/notes", headers=bearer(resp),
                       json={"body": "Memulai eradikasi."})
    assert note.status_code == 201

    # Detail memuat alert anggota + linimasa (note terbaru dulu).
    detail = client.get(f"/incidents/{iid}", headers=bearer(resp)).json()
    assert len(detail["alerts"]) >= 1
    kinds = [n["kind"] for n in detail["notes"]]
    assert "note" in kinds and "status" in kinds and "assign" in kinds


def test_incident_rbac(client, make_user, db_session):
    a3 = _token(client, make_user, "a3", Role.ANALYST_T3)
    _seed_and_correlate(client, db_session, a3)
    client.post("/incidents/correlate", headers=bearer(a3))

    # Analis T1: boleh baca, tak boleh korelasi/kelola.
    t1 = _token(client, make_user, "t1", Role.ANALYST_T1)
    assert client.get("/incidents", headers=bearer(t1)).status_code == 200
    assert client.post("/incidents/correlate", headers=bearer(t1)).status_code == 403
    iid = client.get("/incidents", headers=bearer(a3)).json()["items"][0]["id"]
    assert client.post(f"/incidents/{iid}/assign", headers=bearer(t1), json={}).status_code == 403

    # Auditor: read-only, tak boleh kelola.
    aud = _token(client, make_user, "aud", Role.AUDITOR)
    assert client.get("/incidents", headers=bearer(aud)).status_code == 200
    assert client.post(f"/incidents/{iid}/status", headers=bearer(aud),
                       json={"status": "closed"}).status_code == 403
