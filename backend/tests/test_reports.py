"""Test ELANG-6 Reporter: generate/approve/jadwal + ekspor PDF + RBAC + audit (M9)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app import audit as audit_svc
from app.core.rbac import Role
from app.correlation import correlate
from app.detection import run_detection, seed_rules
from app.intel.samples import seed_intel
from app.models.audit import AuditEntry
from app.models.incident import Incident
from app.models.report import Report, ReportSchedule, ReportStatus
from app.reports import service as svc
from app.simulator import run_all_scenarios, seed_assets

from tests.conftest import bearer, login


def _prepare(db):
    seed_assets(db, record_audit=False)
    run_all_scenarios(db, record_audit=False)
    seed_intel(db, record_audit=False)
    seed_rules(db)
    run_detection(db, record_audit=False)
    correlate(db, record_audit=False)


# --- Generasi (unit) ---

def test_generate_daily_is_draft(db_session):
    _prepare(db_session)
    r = svc.generate_report(db_session, kind="daily", actor="responder", record_audit=False)
    assert r.code.startswith("REP-")
    assert r.status == ReportStatus.DRAFT.value   # wajib review manusia
    assert r.data["incidents_in_period"] >= 0
    assert "coverage_pct" in r.data


def test_generate_executive_has_kpis(db_session):
    _prepare(db_session)
    r = svc.generate_report(db_session, kind="executive", actor="commander", record_audit=False)
    assert "kpis" in r.data
    assert r.data["kpis"]["coverage_pct"]["target"] == 50.0


def test_generate_incident_report(db_session):
    _prepare(db_session)
    inc = db_session.execute(select(Incident)).scalars().first()
    r = svc.generate_report(
        db_session, kind="incident", incident_id=inc.id, actor="responder", record_audit=False
    )
    assert r.incident_id == inc.id
    assert r.data["incident_code"] == inc.incident_code
    assert "timeline" in r.data


def test_generate_compliance_maps_controls(db_session):
    _prepare(db_session)
    r = svc.generate_report(db_session, kind="compliance", actor="commander", record_audit=False)
    assert r.data["audit_ok"] in (True, False)
    assert len(r.data["controls"]) >= 5


def test_incident_report_requires_id(db_session):
    _prepare(db_session)
    try:
        svc.generate_report(db_session, kind="incident", actor="x", record_audit=False)
        assert False, "harus ValueError tanpa incident_id"
    except ValueError:
        pass


# --- PDF ---

def test_pdf_render_is_valid(db_session):
    _prepare(db_session)
    r = svc.generate_report(db_session, kind="monthly", actor="commander", record_audit=False)
    pdf = svc.render_report_pdf(r)
    assert pdf.startswith(b"%PDF-1.")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert b"/Type /Catalog" in pdf
    assert len(pdf) > 500


def test_pdf_render_executive_and_incident(db_session):
    _prepare(db_session)
    inc = db_session.execute(select(Incident)).scalars().first()
    for kind, kwargs in (("executive", {}), ("incident", {"incident_id": inc.id})):
        r = svc.generate_report(db_session, kind=kind, actor="commander", record_audit=False, **kwargs)
        pdf = svc.render_report_pdf(r)
        assert pdf.startswith(b"%PDF-1.")


# --- Approval + audit ---

def test_approve_sets_status_and_audits(db_session):
    _prepare(db_session)
    r = svc.generate_report(db_session, kind="daily", actor="responder")  # audit on
    before = db_session.execute(select(func.count(AuditEntry.id))).scalar()
    approved = svc.approve_report(db_session, report_id=r.id, approver="commander")
    assert approved.status == ReportStatus.APPROVED.value
    assert approved.approved_by == "commander"
    after = db_session.execute(select(func.count(AuditEntry.id))).scalar()
    assert after == before + 1
    # Rantai audit tetap utuh.
    assert audit_svc.verify_chain(db_session)["ok"] is True


# --- Jadwal ---

def test_run_due_schedules_generates(db_session):
    _prepare(db_session)
    sch = ReportSchedule(
        name="harian", kind="daily", cadence="daily",
        next_run_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1),
        created_by="commander",
    )
    db_session.add(sch)
    db_session.commit()
    res = svc.run_due_schedules(db_session, actor="system")
    assert res["ran"] == 1
    assert res["reports"][0].startswith("REP-")
    # next_run_at maju ke depan.
    db_session.refresh(sch)
    assert sch.next_run_at > datetime.now(timezone.utc).replace(tzinfo=None)


def test_run_due_skips_future_schedule(db_session):
    _prepare(db_session)
    sch = ReportSchedule(
        name="besok", kind="daily", cadence="daily",
        next_run_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
        created_by="commander",
    )
    db_session.add(sch)
    db_session.commit()
    res = svc.run_due_schedules(db_session, actor="system")
    assert res["ran"] == 0


# --- API + RBAC ---

def test_api_generate_approve_download(client, make_user, db_session):
    _prepare(db_session)
    make_user("cmd", Role.COMMANDER)
    tok = login(client, "cmd", "Password123!")["access_token"]

    # Generate.
    g = client.post("/reports", json={"kind": "daily"}, headers=bearer(tok))
    assert g.status_code == 201
    rid = g.json()["id"]
    assert g.json()["status"] == "draft"

    # Approve.
    a = client.post(f"/reports/{rid}/approve", headers=bearer(tok))
    assert a.status_code == 200
    assert a.json()["status"] == "approved"

    # Download PDF.
    p = client.get(f"/reports/{rid}/pdf", headers=bearer(tok))
    assert p.status_code == 200
    assert p.headers["content-type"] == "application/pdf"
    assert p.content.startswith(b"%PDF-1.")


def test_rbac_analyst_t1_cannot_generate(client, make_user, db_session):
    _prepare(db_session)
    make_user("a1", Role.ANALYST_T1)
    make_user("aud", Role.AUDITOR)
    tok1 = login(client, "a1", "Password123!")["access_token"]
    # T1 boleh baca tapi tak boleh generate.
    assert client.get("/reports", headers=bearer(tok1)).status_code == 200
    assert client.post("/reports", json={"kind": "daily"}, headers=bearer(tok1)).status_code == 403

    # Auditor read-only: boleh baca, tak boleh generate/approve.
    tokA = login(client, "aud", "Password123!")["access_token"]
    assert client.get("/reports", headers=bearer(tokA)).status_code == 200
    assert client.post("/reports", json={"kind": "compliance"}, headers=bearer(tokA)).status_code == 403


def test_rbac_only_approver_can_approve(client, make_user, db_session):
    _prepare(db_session)
    make_user("resp", Role.RESPONDER)
    tok = login(client, "resp", "Password123!")["access_token"]
    # Responder boleh generate (laporan insiden) tapi tak boleh approve.
    g = client.post("/reports", json={"kind": "daily"}, headers=bearer(tok))
    assert g.status_code == 201
    rid = g.json()["id"]
    assert client.post(f"/reports/{rid}/approve", headers=bearer(tok)).status_code == 403
