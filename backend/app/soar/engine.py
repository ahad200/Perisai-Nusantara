"""Mesin SOAR (PRD M8, FR-301/302/304/306).

Menjalankan playbook untuk sebuah insiden. Untuk tiap langkah, **Matriks Otonomi**
(§7) memutuskan auto atau approval. Mode `dry_run` menjalankan tanpa efek nyata
(FR-306). Aksi yang dieksekusi dapat di-**rollback** (FR-304). Hanya mesin ini
yang memanggil adapter (§A.5 no.1); semua adapter mock (§A.5 no.8).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models.alert import Alert
from app.models.asset import Asset, Criticality, resolve_criticality
from app.models.detection import SEVERITY_RANK
from app.models.incident import Incident
from app.models.soar import (
    ActionExecution,
    ActionStatus,
    Approval,
    ApprovalStatus,
    Playbook,
    PlaybookRun,
    RunMode,
    RunStatus,
)
from app.soar import autonomy
from app.soar.adapters import get_adapter, spec_for
from app.soar.notify import active_break_glass, notify


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_criticality(db: Session, incident: Incident) -> str:
    crit = None
    if incident.asset_id is not None:
        crit = db.execute(
            select(Asset.criticality).where(Asset.id == incident.asset_id)
        ).scalar_one_or_none()
    return resolve_criticality(crit).value  # fail-safe K1 (§A.5 no.6)


def _pick_playbook(db: Session, incident: Incident) -> Playbook | None:
    """Playbook untuk teknik dari alert ber-severity tertinggi yang punya playbook.

    Mis. insiden ransomware berisi T1036 (high) + T1486 (critical) → playbook T1486.
    Fallback: urutan teknik pada insiden.
    """
    from app.soar.playbooks import playbook_for_technique

    rows = db.execute(
        select(Alert.technique, Alert.severity)
        .where(Alert.incident_id == incident.id)
        .order_by(Alert.id)
    ).all()
    ranked = [t for t, _ in sorted(rows, key=lambda r: -SEVERITY_RANK.get(r[1], 0)) if t]
    fallback = [t["technique"] for t in incident.techniques or []]
    for tech in dict.fromkeys([*ranked, *fallback]):
        pb = playbook_for_technique(db, tech)
        if pb is not None:
            return pb
    return None


def _audit_action(db, actor, ae: ActionExecution, action: str, payload: dict) -> None:
    audit.record(db, action=action, actor_type="user", actor_id=actor,
                 object_type="action_execution", object_id=str(ae.id), payload=payload)


def _execute(db: Session, ae: ActionExecution, *, actor: str) -> None:
    """Jalankan satu aksi lewat adapter (mock) dan tandai EXECUTED. Menulis audit."""
    adapter = get_adapter(ae.action)
    result = adapter.execute(ae.action, ae.params or {})
    ae.status = ActionStatus.EXECUTED.value
    ae.result = result
    _audit_action(db, actor, ae, "soar.action.execute",
                  {"action": ae.action, "params": ae.params, "mock": True})


def run_playbook(
    db: Session, *, incident_id: int, playbook_code: str | None = None,
    mode: str = RunMode.AUTO.value, actor: str = "operator", record_audit: bool = True,
) -> PlaybookRun:
    """Jalankan playbook untuk insiden. Kembalikan PlaybookRun (dengan ActionExecution)."""
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise ValueError("Insiden tidak ditemukan")

    # Pilih playbook: eksplisit, atau dari teknik alert ber-severity tertinggi.
    pb: Playbook | None = None
    if playbook_code:
        pb = db.execute(select(Playbook).where(Playbook.code == playbook_code)).scalars().first()
    if pb is None:
        pb = _pick_playbook(db, incident)
    if pb is None:
        raise ValueError("Tidak ada playbook yang cocok untuk insiden ini")

    severity = incident.severity
    criticality = _resolve_criticality(db, incident)
    dry = mode == RunMode.DRY_RUN.value
    bg = None if dry else active_break_glass(db)

    run = PlaybookRun(
        playbook_id=pb.id, playbook_code=pb.code, incident_id=incident_id,
        mode=mode, status=RunStatus.RUNNING.value, severity=severity,
        criticality=criticality, host=incident.host, actor=actor,
    )
    db.add(run)
    db.flush()

    counts = {"executed": 0, "awaiting_approval": 0, "simulated": 0}
    for idx, step in enumerate(pb.steps):
        action = step["action"]
        spec = spec_for(action)
        disruptive = bool(step.get("disruptive", spec.disruptive))
        pre_approved = bool(step.get("pre_approved", False))
        params = dict(step.get("params") or {})
        if incident.host and "host" not in params:
            params["host"] = incident.host

        decision = autonomy.decide(
            severity, criticality, disruptive=disruptive,
            pre_approved=pre_approved, break_glass=bool(bg),
        )

        ae = ActionExecution(
            run_id=run.id, incident_id=incident_id, step_index=idx, action=action,
            params=params, disruptive=disruptive, pre_approved=pre_approved,
            reversible=spec.reversible, decision_mode=decision.mode,
            decision_reason=decision.reason,
        )
        db.add(ae)
        db.flush()

        if dry:
            ae.status = ActionStatus.SIMULATED.value
            ae.result = {"dry_run": True, "would": decision.mode, "decision": decision.reason}
            counts["simulated"] += 1
            continue

        if decision.mode == "auto":
            _execute(db, ae, actor=actor)
            counts["executed"] += 1
            if decision.notify_commander:
                notify(db, recipient_role="commander", kind="soar_auto",
                       title=f"Aksi otomatis: {action}", body=decision.reason,
                       ref_type="run", ref_id=run.id, commit=False)
        else:
            deadline = None
            if decision.timeout_minutes:
                deadline = _utcnow() + timedelta(minutes=decision.timeout_minutes)
            approval = Approval(
                action_execution_id=ae.id, run_id=run.id, incident_id=incident_id,
                action=action, severity=severity, criticality=criticality,
                required_tier=decision.required_tier or "commander",
                on_timeout=decision.on_timeout or "escalate",
                status=ApprovalStatus.PENDING.value, deadline=deadline,
            )
            db.add(approval)
            db.flush()
            ae.status = ActionStatus.AWAITING_APPROVAL.value
            ae.approval_id = approval.id
            counts["awaiting_approval"] += 1
            notify(db, recipient_role=approval.required_tier, kind="soar_approval",
                   title=f"Approval diperlukan: {action}", body=decision.reason,
                   ref_type="approval", ref_id=approval.id, commit=False)

    run.status = (
        RunStatus.AWAITING_APPROVAL.value if counts["awaiting_approval"]
        else RunStatus.COMPLETED.value
    )
    run.summary = {"playbook": pb.code, "steps": len(pb.steps),
                   "break_glass": bool(bg), **counts}

    if record_audit:
        audit.record(db, action="soar.run", actor_type="user", actor_id=actor,
                     object_type="playbook_run", object_id=str(run.id),
                     payload={"playbook": pb.code, "incident_id": incident_id,
                              "mode": mode, "severity": severity,
                              "criticality": criticality, **counts})
    db.commit()
    db.refresh(run)
    return run


def rollback_run(db: Session, *, run_id: int, actor: str, record_audit: bool = True) -> dict[str, Any]:
    """Rollback semua aksi yang telah dieksekusi & reversibel pada sebuah run (FR-304)."""
    run = db.get(PlaybookRun, run_id)
    if run is None:
        raise ValueError("Run tidak ditemukan")

    aes = db.execute(
        select(ActionExecution).where(ActionExecution.run_id == run_id)
        .order_by(ActionExecution.step_index.desc())
    ).scalars().all()

    rolled = skipped = 0
    for ae in aes:
        if ae.status == ActionStatus.EXECUTED.value and ae.reversible and not ae.rolled_back:
            adapter = get_adapter(ae.action)
            res = adapter.rollback(ae.action, ae.params or {}, ae.result)
            ae.rolled_back = True
            ae.status = ActionStatus.ROLLED_BACK.value
            ae.result = {"executed": ae.result, "rollback": res}
            _audit_action(db, actor, ae, "soar.action.rollback",
                          {"action": ae.action, "mock": True})
            rolled += 1
        else:
            skipped += 1

    run.status = RunStatus.ROLLED_BACK.value
    if record_audit:
        audit.record(db, action="soar.rollback", actor_type="user", actor_id=actor,
                     object_type="playbook_run", object_id=str(run_id),
                     payload={"rolled_back": rolled, "skipped": skipped})
    db.commit()
    db.refresh(run)
    return {"run_id": run_id, "rolled_back": rolled, "skipped": skipped, "status": run.status}
