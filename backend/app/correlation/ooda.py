"""Alur investigasi OODA per insiden (Observe → Orient → Decide → Act).

Read-only dan deterministik: hanya **menyusun ulang** data yang sudah tercatat
(alert, teknik ATT&CK, kritikalitas aset, hipotesis atribusi, keputusan Matriks
Otonomi, approval, eksekusi aksi SOAR). Tidak memanggil LLM, tidak mengubah state,
tidak memanggil adapter (PRD §A.5 no.1).

Pemetaan fase:
- **Observe** — alert anggota insiden (FP yang ditutup disembunyikan).
- **Orient**  — teknik ATT&CK, kritikalitas aset (fail-safe K1, §A.5 no.6),
  hipotesis atribusi ELANG-3 (+ status validasi).
- **Decide**  — keputusan Matriks Otonomi per langkah playbook + approval.
- **Act**     — hasil eksekusi aksi (executed/simulated/rolled_back/…) +
  perubahan status insiden (contained/closed).

Status fase: ``empty`` (belum ada catatan), ``recorded`` (ada catatan), atau
``waiting`` (ada yang menunggu keputusan manusia — approval tertunda, atau
hipotesis yang belum divalidasi).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertStatus
from app.models.asset import Asset, resolve_criticality
from app.models.attribution import AttributionHypothesis, ValidationStatus
from app.models.incident import Incident, IncidentNote, IncidentStatus, NoteKind
from app.models.soar import ActionExecution, ActionStatus, Approval, ApprovalStatus, PlaybookRun

PHASES = ("observe", "orient", "decide", "act")

_ACT_STATUSES = {
    ActionStatus.EXECUTED.value,
    ActionStatus.SIMULATED.value,
    ActionStatus.ROLLED_BACK.value,
    ActionStatus.FAILED.value,
    ActionStatus.DENIED.value,
}


def _item(ts: datetime | None, kind: str, ref: str, text: str, *,
          status: str | None = None, severity: str | None = None) -> dict[str, Any]:
    return {"ts": ts, "kind": kind, "ref": ref, "text": text, "status": status, "severity": severity}


def _sort_key(it: dict) -> tuple:
    ts = it["ts"]
    # Item tanpa waktu (mis. teknik ATT&CK) di depan, lalu kronologis.
    return (ts is not None, ts.replace(tzinfo=None) if ts else datetime.min, it["ref"])


def build_ooda(db: Session, incident: Incident) -> dict[str, Any]:
    inc_id = incident.id

    # --- Observe ---------------------------------------------------------- #
    alerts = db.execute(
        select(Alert).where(
            Alert.incident_id == inc_id, Alert.status != AlertStatus.CLOSED_FP.value,
        ).order_by(Alert.first_event_ts.asc(), Alert.id.asc())
    ).scalars().all()
    observe = [
        _item(a.first_event_ts or a.created_at, "alert", f"ALERT-{a.id}",
              f"{a.rule_code} · {a.title}"
              + (f" ({a.event_count} event)" if a.event_count else ""),
              status=a.status, severity=a.severity)
        for a in alerts
    ]

    # --- Orient ----------------------------------------------------------- #
    crit_raw = None
    if incident.asset_id is not None:
        crit_raw = db.execute(
            select(Asset.criticality).where(Asset.id == incident.asset_id)
        ).scalar_one_or_none()
    criticality = resolve_criticality(crit_raw).value  # fail-safe K1 (§A.5 no.6)
    crit_note = "" if crit_raw else " (tak tercatat → fail-safe K1)"

    orient = [
        _item(None, "technique", t.get("technique") or "-",
              f"{t.get('technique')}" + (f" · {t['name']}" if t.get("name") else ""))
        for t in (incident.techniques or [])
    ]
    orient.append(_item(None, "criticality", f"ASSET-{incident.asset_id or '-'}",
                        f"Kritikalitas aset {incident.host or '-'}: {criticality}{crit_note}",
                        status=criticality))
    hyps = db.execute(
        select(AttributionHypothesis).where(AttributionHypothesis.incident_id == inc_id)
        .order_by(AttributionHypothesis.id.asc())
    ).scalars().all()
    for h in hyps:
        orient.append(_item(
            h.created_at, "attribution", f"HYP-{h.id}",
            f"Hipotesis {h.created_by}: {h.actor} (confidence {h.confidence})",
            status=h.status,
        ))

    # --- Decide & Act ----------------------------------------------------- #
    runs = db.execute(
        select(PlaybookRun).where(PlaybookRun.incident_id == inc_id).order_by(PlaybookRun.id.asc())
    ).scalars().all()
    run_ids = [r.id for r in runs]
    run_by_id = {r.id: r for r in runs}
    actions = db.execute(
        select(ActionExecution).where(ActionExecution.run_id.in_(run_ids))
        .order_by(ActionExecution.run_id.asc(), ActionExecution.step_index.asc())
    ).scalars().all() if run_ids else []
    approvals = db.execute(
        select(Approval).where(Approval.run_id.in_(run_ids)).order_by(Approval.id.asc())
    ).scalars().all() if run_ids else []

    decide: list[dict] = []
    act: list[dict] = []
    for ae in actions:
        run = run_by_id[ae.run_id]
        tag = " [dry-run]" if run.mode == "dry_run" else ""
        decide.append(_item(
            ae.created_at, "decision", f"RUN-{run.id}/{ae.step_index}",
            f"{run.playbook_code} · {ae.action}: {ae.decision_mode or '-'}{tag}"
            + (f" — {ae.decision_reason}" if ae.decision_reason else ""),
            status=ae.decision_mode or None,
        ))
        if ae.status in _ACT_STATUSES:
            act.append(_item(
                ae.updated_at or ae.created_at, "action", f"ACT-{ae.id}",
                f"{ae.action} → {ae.status}{tag}"
                + (" (di-rollback)" if ae.rolled_back and ae.status != ActionStatus.ROLLED_BACK.value else ""),
                status=ae.status,
            ))
    for ap in approvals:
        who = f" oleh {ap.approver}" if ap.approver else ""
        decide.append(_item(
            ap.resolved_at or ap.requested_at, "approval", f"APR-{ap.id}",
            f"Approval {ap.action} ({ap.severity}×{ap.criticality}) → {ap.required_tier}: {ap.status}{who}",
            status=ap.status,
        ))

    # Perubahan status insiden ke contained/closed = hasil tindakan.
    status_notes = db.execute(
        select(IncidentNote).where(
            IncidentNote.incident_id == inc_id, IncidentNote.kind == NoteKind.STATUS.value,
        ).order_by(IncidentNote.created_at.asc(), IncidentNote.id.asc())
    ).scalars().all()
    for n in status_notes:
        if f"-> {IncidentStatus.CONTAINED.value}" in n.body or f"-> {IncidentStatus.CLOSED.value}" in n.body:
            act.append(_item(n.created_at, "status", f"NOTE-{n.id}", f"{n.body} ({n.author})",
                             status="status"))

    # --- Status fase ------------------------------------------------------ #
    pending_approvals = sum(1 for ap in approvals if ap.status == ApprovalStatus.PENDING.value)
    awaiting_actions = sum(1 for ae in actions if ae.status == ActionStatus.AWAITING_APPROVAL.value)
    unvalidated = sum(1 for h in hyps if h.status == ValidationStatus.PROPOSED.value)

    def _phase(key: str, items: list[dict], waiting: str | None) -> dict:
        items.sort(key=_sort_key)
        state = "waiting" if waiting else ("recorded" if items else "empty")
        return {"key": key, "state": state, "waiting_reason": waiting, "items": items}

    phases = [
        _phase("observe", observe, None),
        _phase("orient", orient,
               f"{unvalidated} hipotesis atribusi belum divalidasi intel" if unvalidated else None),
        _phase("decide", decide,
               f"{pending_approvals} approval menunggu keputusan" if pending_approvals else None),
        _phase("act", act,
               f"{awaiting_actions} aksi ditahan menunggu approval" if awaiting_actions else None),
    ]

    if incident.status == IncidentStatus.CLOSED.value:
        current = "closed"
    else:
        current = next(
            (p["key"] for p in phases if p["state"] in ("empty", "waiting")), "act",
        )

    return {
        "incident_id": inc_id,
        "incident_code": incident.incident_code,
        "incident_status": incident.status,
        "severity": incident.severity,
        "criticality": criticality,
        "current_phase": current,
        "phases": phases,
    }
