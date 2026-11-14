"""Layanan ELANG-6 (Reporter, template deterministik F1): hasilkan laporan,
setujui (review manusia wajib sebelum kirim eksternal), jalankan jadwal jatuh
tempo, dan render PDF.

Setiap perubahan state (hasilkan/approve/jadwal) menulis AuditEntry (§A.5 no.3).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit as audit_svc
from app.models.alert import Alert
from app.models.detection import DetectionRule
from app.models.incident import Incident, IncidentNote
from app.models.report import Report, ReportCadence, ReportKind, ReportSchedule, ReportStatus
from app.models.soar import ActionExecution, PlaybookRun
from app.reports import coverage as coverage_mod
from app.reports import metrics as metrics_mod
from app.reports.pdf import PdfReport

_CADENCE_DAYS = {
    ReportCadence.DAILY.value: 1,
    ReportCadence.WEEKLY.value: 7,
    ReportCadence.MONTHLY.value: 30,
}
_PERIOD_DAYS = {
    ReportKind.DAILY.value: 1,
    ReportKind.WEEKLY.value: 7,
    ReportKind.MONTHLY.value: 30,
    ReportKind.EXECUTIVE.value: 30,
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


# --------------------------------------------------------------------------- #
# Komputasi isi laporan (deterministik)                                       #
# --------------------------------------------------------------------------- #
def _period_data(db: Session, *, kind: str, start: datetime, end: datetime) -> dict:
    alerts = int(
        db.execute(
            select(func.count(Alert.id)).where(Alert.created_at >= start, Alert.created_at < end)
        ).scalar()
        or 0
    )
    incidents = int(
        db.execute(
            select(func.count(Incident.id)).where(
                Incident.created_at >= start, Incident.created_at < end
            )
        ).scalar()
        or 0
    )
    situasi = metrics_mod.situasi_snapshot(db, now=end)
    cov = coverage_mod.coverage_matrix(db)
    key = metrics_mod._key_incidents(db, start=start, now=end)
    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "alerts_in_period": alerts,
        "incidents_in_period": incidents,
        "posture": situasi["posture"],
        "active_incidents": situasi["active_incidents"],
        "incidents_by_severity": situasi["incidents_by_severity"],
        "pending_approvals": situasi["pending_approvals"],
        "coverage_pct": cov["coverage_pct"],
        "coverage_gaps": cov["gaps"],
        "data_sources": situasi["data_sources"],
        "key_incidents": key,
    }


def _incident_data(db: Session, incident: Incident) -> dict:
    notes = (
        db.execute(
            select(IncidentNote)
            .where(IncidentNote.incident_id == incident.id)
            .order_by(IncidentNote.created_at.asc())
        )
        .scalars()
        .all()
    )
    alerts = (
        db.execute(
            select(Alert).where(Alert.incident_id == incident.id).order_by(Alert.created_at.asc())
        )
        .scalars()
        .all()
    )
    runs = (
        db.execute(
            select(PlaybookRun)
            .where(PlaybookRun.incident_id == incident.id)
            .order_by(PlaybookRun.created_at.asc())
        )
        .scalars()
        .all()
    )
    run_ids = [r.id for r in runs]
    actions = []
    if run_ids:
        actions = (
            db.execute(
                select(ActionExecution)
                .where(ActionExecution.run_id.in_(run_ids))
                .order_by(ActionExecution.id.asc())
            )
            .scalars()
            .all()
        )
    return {
        "incident_code": incident.incident_code,
        "title": incident.title,
        "severity": incident.severity,
        "status": incident.status,
        "host": incident.host,
        "assignee": incident.assignee,
        "alert_count": incident.alert_count,
        "techniques": [
            t.get("technique") if isinstance(t, dict) else t for t in (incident.techniques or [])
        ],
        "first_event_ts": _naive(incident.first_event_ts).isoformat() if incident.first_event_ts else None,
        "last_event_ts": _naive(incident.last_event_ts).isoformat() if incident.last_event_ts else None,
        "created_at": _naive(incident.created_at).isoformat() if incident.created_at else None,
        "timeline": [
            {
                "at": _naive(n.created_at).isoformat() if n.created_at else None,
                "author": n.author,
                "kind": n.kind,
                "body": n.body,
            }
            for n in notes
        ],
        "alerts": [
            {
                "severity": a.severity,
                "technique": a.technique,
                "title": a.title,
                "status": a.status,
            }
            for a in alerts
        ],
        "actions": [
            {
                "action": a.action,
                "status": a.status,
                "decision_mode": a.decision_mode,
                "disruptive": a.disruptive,
                "rolled_back": a.rolled_back,
            }
            for a in actions
        ],
    }


# Peta kontrol kepatuhan -> bukti dari platform (FR-604). Statis/deterministik (F1).
_COMPLIANCE_CONTROLS = [
    ("ISO 27001 A.5.15", "Access control (RBAC)", "rbac_roles"),
    ("ISO 27001 A.8.15", "Logging (audit immutable)", "audit_chain"),
    ("ISO 27001 A.5.25", "Assessment & decision on events", "incidents"),
    ("ISO 27001 A.5.26", "Response to incidents (SOAR)", "playbook_runs"),
    ("NIST CSF DE.CM", "Continuous monitoring (detection)", "detection_rules"),
    ("NIST CSF RS.MI", "Mitigation (playbook actions)", "actions"),
    ("NIST CSF PR.AC", "Identity & MFA", "mfa"),
]


def _compliance_data(db: Session) -> dict:
    verify = audit_svc.verify_chain(db)
    rules = int(db.execute(select(func.count(DetectionRule.id))).scalar() or 0)
    incidents = int(db.execute(select(func.count(Incident.id))).scalar() or 0)
    runs = int(db.execute(select(func.count(PlaybookRun.id))).scalar() or 0)
    actions = int(db.execute(select(func.count(ActionExecution.id))).scalar() or 0)
    evidence = {
        "rbac_roles": "9 role dengan pemisahan tugas (auditor read-only)",
        "audit_chain": f"hash chain {'UTUH' if verify['ok'] else 'RUSAK'} — {verify['count']} entri",
        "incidents": f"{incidents} insiden terkorelasi",
        "playbook_runs": f"{runs} eksekusi playbook tercatat",
        "detection_rules": f"{rules} aturan deteksi",
        "actions": f"{actions} aksi respons (semua teraudit)",
        "mfa": "MFA (TOTP) + JWT aktif di semua endpoint",
    }
    controls = [
        {"control": c, "name": name, "evidence": evidence.get(key, "")}
        for c, name, key in _COMPLIANCE_CONTROLS
    ]
    return {"audit_ok": verify["ok"], "audit_count": verify["count"], "controls": controls}


# --------------------------------------------------------------------------- #
# Operasi utama                                                               #
# --------------------------------------------------------------------------- #
def generate_report(
    db: Session,
    *,
    kind: str,
    actor: str = "system",
    incident_id: int | None = None,
    now: datetime | None = None,
    schedule_id: int | None = None,
    record_audit: bool = True,
) -> Report:
    now = now or _now()
    kind = ReportKind(kind).value
    data: dict
    period_start = period_end = None

    if kind == ReportKind.INCIDENT.value:
        if incident_id is None:
            raise ValueError("incident_id wajib untuk laporan insiden")
        incident = db.get(Incident, incident_id)
        if incident is None:
            raise ValueError(f"insiden {incident_id} tak ditemukan")
        data = _incident_data(db, incident)
        title = f"Laporan Insiden {incident.incident_code} — {incident.title}"[:200]
        summary = f"{incident.severity.upper()} · {incident.status} · {incident.alert_count} alert"
    elif kind == ReportKind.EXECUTIVE.value:
        data = metrics_mod.executive_kpis(db, days=30, now=now)
        period_start = now - timedelta(days=30)
        period_end = now
        title = "Ringkasan Eksekutif — 30 Hari"
        k = data["kpis"]
        summary = (
            f"MTTD {k['mttd_minutes']['value']}m · MTTR {k['mttr_minutes']['value']}m · "
            f"Coverage {k['coverage_pct']['value']}%"
        )
    elif kind == ReportKind.COMPLIANCE.value:
        data = _compliance_data(db)
        title = "Laporan Kepatuhan — ISO 27001 / NIST CSF 2.0"
        summary = f"{len(data['controls'])} kontrol · audit {'utuh' if data['audit_ok'] else 'RUSAK'}"
    else:  # daily/weekly/monthly
        days = _PERIOD_DAYS[kind]
        period_start = now - timedelta(days=days)
        period_end = now
        data = _period_data(db, kind=kind, start=period_start, end=period_end)
        label = {"daily": "Harian", "weekly": "Mingguan", "monthly": "Bulanan"}[kind]
        title = f"Laporan SOC {label} — {period_start.date()} s/d {period_end.date()}"
        summary = (
            f"{data['incidents_in_period']} insiden · {data['alerts_in_period']} alert · "
            f"postur {data['posture']}"
        )

    report = Report(
        code="REP-PENDING",
        kind=kind,
        title=title,
        period_start=period_start,
        period_end=period_end,
        incident_id=incident_id,
        status=ReportStatus.DRAFT.value,
        data=data,
        summary=summary[:1024],
        generated_by=actor,
        schedule_id=schedule_id,
    )
    db.add(report)
    db.flush()
    report.code = f"REP-{report.id:05d}"
    db.commit()
    db.refresh(report)

    if record_audit:
        audit_svc.record(
            db,
            action="report.generate",
            actor_type="user",
            actor_id=actor,
            object_type="report",
            object_id=report.code,
            payload={"kind": kind, "incident_id": incident_id, "schedule_id": schedule_id},
        )
    return report


def approve_report(db: Session, *, report_id: int, approver: str) -> Report:
    """Review manusia wajib sebelum laporan dikirim ke pihak eksternal (PRD §6/§10)."""
    report = db.get(Report, report_id)
    if report is None:
        raise ValueError(f"laporan {report_id} tak ditemukan")
    if report.status != ReportStatus.APPROVED.value:
        report.status = ReportStatus.APPROVED.value
        report.approved_by = approver
        report.approved_at = _now()
        db.commit()
        db.refresh(report)
        audit_svc.record(
            db,
            action="report.approve",
            actor_type="user",
            actor_id=approver,
            object_type="report",
            object_id=report.code,
        )
    return report


def run_due_schedules(db: Session, *, now: datetime | None = None, actor: str = "system") -> dict:
    """Hasilkan laporan untuk jadwal yang jatuh tempo (`next_run_at <= now`)."""
    now = now or _now()
    due = (
        db.execute(
            select(ReportSchedule)
            .where(ReportSchedule.enabled.is_(True))
            .where(ReportSchedule.next_run_at <= now)
            .order_by(ReportSchedule.id.asc())
        )
        .scalars()
        .all()
    )
    generated: list[str] = []
    for sch in due:
        report = generate_report(db, kind=sch.kind, actor=actor, now=now, schedule_id=sch.id)
        sch.last_run_at = now
        sch.next_run_at = now + timedelta(days=_CADENCE_DAYS.get(sch.cadence, 1))
        db.commit()
        generated.append(report.code)
    return {"ran": len(generated), "reports": generated}


# --------------------------------------------------------------------------- #
# Render PDF                                                                   #
# --------------------------------------------------------------------------- #
def render_report_pdf(report: Report) -> bytes:
    pdf = PdfReport()
    pdf.title(report.title)
    pdf.kv("Kode", report.code)
    pdf.kv("Jenis", report.kind)
    pdf.kv("Status", report.status + (" — DRAF, belum disetujui" if report.status == "draft" else ""))
    pdf.kv("Dihasilkan oleh", report.generated_by or "-")
    if report.approved_by:
        pdf.kv("Disetujui oleh", report.approved_by)
    pdf.kv("Ringkasan", report.summary or "-")
    pdf.spacer(4)

    d = report.data or {}
    kind = report.kind
    if kind == ReportKind.INCIDENT.value:
        _render_incident(pdf, d)
    elif kind == ReportKind.EXECUTIVE.value:
        _render_executive(pdf, d)
    elif kind == ReportKind.COMPLIANCE.value:
        _render_compliance(pdf, d)
    else:
        _render_period(pdf, d)

    if report.status != ReportStatus.APPROVED.value:
        pdf.spacer(6)
        pdf.rule()
        pdf.paragraph(
            "DRAF — laporan ini belum disetujui manusia. Dilarang dikirim ke pihak "
            "eksternal sebelum persetujuan (PRD §6, §10)."
        )
    return pdf.render()


def _render_period(pdf: PdfReport, d: dict) -> None:
    pdf.heading("Postur & Volume")
    pdf.kv("Postur", str(d.get("posture", "-")))
    pdf.kv("Insiden pada periode", str(d.get("incidents_in_period", 0)))
    pdf.kv("Alert pada periode", str(d.get("alerts_in_period", 0)))
    pdf.kv("Insiden aktif", str(d.get("active_incidents", 0)))
    pdf.kv("Approval tertunda", str(d.get("pending_approvals", 0)))
    sev = d.get("incidents_by_severity", {})
    pdf.kv("Insiden aktif/severity", ", ".join(f"{k}:{v}" for k, v in sev.items()))
    pdf.kv("Coverage ATT&CK", f"{d.get('coverage_pct', 0)}%")

    gaps = d.get("coverage_gaps", [])
    if gaps:
        pdf.heading("Gap Deteksi (teknik prioritas tanpa deteksi)")
        pdf.table(
            ["Taktik", "Teknik", "Nama"],
            [[g["tactic"], g["id"], g["name"]] for g in gaps],
            widths=[2, 1, 3],
        )

    key = d.get("key_incidents", [])
    if key:
        pdf.heading("Insiden Penting")
        pdf.table(
            ["Kode", "Severity", "Status", "Host", "Alert"],
            [[k["incident_code"], k["severity"], k["status"], k.get("host") or "-", str(k["alert_count"])] for k in key],
            widths=[2, 1.3, 1.5, 2.2, 1],
        )

    ds = d.get("data_sources", [])
    if ds:
        pdf.heading("Kesehatan Sumber Data")
        pdf.table(
            ["Sumber", "Event", "Jeda (jam)", "Status"],
            [[s["source"], str(s["events"]), str(s.get("lag_hours")), s["status"]] for s in ds],
            widths=[3, 1.3, 1.5, 1.2],
        )


def _render_executive(pdf: PdfReport, d: dict) -> None:
    k = d.get("kpis", {})
    pdf.heading(f"KPI — {d.get('window_days', 30)} Hari")

    def fmt(metric: str, unit: str = "") -> str:
        m = k.get(metric, {})
        val, prev = m.get("value"), m.get("prev")
        s = f"{val}{unit}" if val is not None else "-"
        if prev is not None:
            s += f"  (sebelumnya {prev}{unit})"
        if m.get("target") is not None:
            s += f"  · target {m['target']}{unit}"
        return s

    pdf.kv("MTTD", fmt("mttd_minutes", " mnt"))
    pdf.kv("MTTR", fmt("mttr_minutes", " mnt"))
    pdf.kv("FP rate", fmt("fp_rate_pct", "%"))
    pdf.kv("Coverage ATT&CK", fmt("coverage_pct", "%"))
    pdf.kv("Insiden", fmt("incidents"))

    key = d.get("key_incidents", [])
    if key:
        pdf.heading("Insiden Penting")
        pdf.table(
            ["Kode", "Severity", "Status", "Host", "Teknik"],
            [
                [k2["incident_code"], k2["severity"], k2["status"], k2.get("host") or "-", ",".join(k2.get("techniques", []))]
                for k2 in key
            ],
            widths=[1.8, 1.2, 1.4, 2, 2],
        )


def _render_compliance(pdf: PdfReport, d: dict) -> None:
    pdf.heading("Pemetaan Kontrol → Bukti")
    pdf.kv("Integritas audit", "UTUH" if d.get("audit_ok") else "RUSAK")
    pdf.kv("Entri audit", str(d.get("audit_count", 0)))
    pdf.spacer(2)
    pdf.table(
        ["Kontrol", "Nama", "Bukti dari platform"],
        [[c["control"], c["name"], c["evidence"]] for c in d.get("controls", [])],
        widths=[1.6, 2, 3.4],
    )


def _wib(iso: str | None) -> str:
    """ISO UTC naif (format data laporan) → 'YYYY-MM-DD HH:MM:SS WIB'."""
    if not iso:
        return "-"
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return (dt + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S WIB")


def _render_incident(pdf: PdfReport, d: dict) -> None:
    pdf.heading("Ringkasan Insiden")
    pdf.kv("Severity", str(d.get("severity", "-")))
    pdf.kv("Status", str(d.get("status", "-")))
    pdf.kv("Host", str(d.get("host") or "-"))
    pdf.kv("Penanggung jawab", str(d.get("assignee") or "-"))
    pdf.kv("Jumlah alert", str(d.get("alert_count", 0)))
    pdf.kv("Teknik ATT&CK", ", ".join(d.get("techniques", [])) or "-")
    pdf.kv("Event pertama", _wib(d.get("first_event_ts")))
    pdf.kv("Event terakhir", _wib(d.get("last_event_ts")))

    tl = d.get("timeline", [])
    if tl:
        pdf.heading("Linimasa")
        pdf.table(
            ["Waktu", "Aktor", "Jenis", "Catatan"],
            [[_wib(t.get("at")), t.get("author") or "-", t.get("kind") or "-", t.get("body") or ""] for t in tl],
            widths=[2.4, 1.4, 1.2, 4],
        )

    acts = d.get("actions", [])
    if acts:
        pdf.heading("Aksi Respons")
        pdf.table(
            ["Aksi", "Status", "Mode", "Disruptif", "Rollback"],
            [
                [a["action"], a["status"], a.get("decision_mode") or "-", "ya" if a["disruptive"] else "tidak", "ya" if a["rolled_back"] else "tidak"]
                for a in acts
            ],
            widths=[2, 1.6, 1.2, 1.2, 1.2],
        )
