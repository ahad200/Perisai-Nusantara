"""Test metrik dashboard Situasi (COP) & Eksekutif (M9)."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.rbac import Role
from app.correlation import correlate
from app.detection import run_detection, seed_rules
from app.intel.samples import seed_intel
from app.models.incident import Incident, IncidentStatus
from app.reports import metrics
from app.simulator import run_all_scenarios, seed_assets

from tests.conftest import bearer, login


def _prepare(db):
    seed_assets(db, record_audit=False)
    run_all_scenarios(db, record_audit=False)
    seed_intel(db, record_audit=False)
    seed_rules(db)
    run_detection(db, record_audit=False)
    correlate(db, record_audit=False)


def test_situasi_snapshot_shape(db_session):
    _prepare(db_session)
    s = metrics.situasi_snapshot(db_session)
    assert s["posture"] in {"critical", "elevated", "guarded", "normal"}
    assert s["active_incidents"] >= 1
    assert set(s["incidents_by_severity"]) == {"critical", "high", "medium", "low"}
    assert len(s["trend_24h"]) == 24
    assert s["data_sources"]  # ada sumber event
    assert s["segments"]      # ada segmen aset


def test_posture_reflects_critical_incident(db_session):
    _prepare(db_session)
    # Ada insiden critical di data simulasi (ransomware) → postur critical.
    has_crit = db_session.execute(
        select(Incident).where(Incident.severity == "critical")
    ).first()
    s = metrics.situasi_snapshot(db_session)
    if has_crit:
        assert s["posture"] == "critical"


def test_executive_kpis_shape_and_comparators(db_session):
    _prepare(db_session)
    k = metrics.executive_kpis(db_session, days=30)["kpis"]
    # Setiap KPI punya pembanding (prev/target) — PRD §C.5.
    assert "value" in k["mttd_minutes"] and "prev" in k["mttd_minutes"]
    assert k["coverage_pct"]["target"] == 50.0
    assert k["coverage_pct"]["value"] >= 0


def test_mttr_computed_when_incident_closed(db_session):
    _prepare(db_session)
    inc = db_session.execute(select(Incident)).scalars().first()
    # Tutup satu insiden: created lebih awal, updated sekarang.
    inc.status = IncidentStatus.CLOSED.value
    inc.created_at = inc.created_at - timedelta(hours=2) if inc.created_at else None
    db_session.commit()
    k = metrics.executive_kpis(db_session, days=30)["kpis"]
    assert k["mttr_minutes"]["value"] is not None
    assert k["mttr_minutes"]["sample"] >= 1


def test_situasi_endpoint_rbac(client, make_user):
    make_user("analyst1", Role.ANALYST_T1)
    tok = login(client, "analyst1", "Password123!")["access_token"]
    # Semua role SOC boleh membaca dashboard.
    r = client.get("/dashboard/situasi", headers=bearer(tok))
    assert r.status_code == 200
    assert "posture" in r.json()
    r2 = client.get("/dashboard/coverage", headers=bearer(tok))
    assert r2.status_code == 200
    assert "coverage_pct" in r2.json()
