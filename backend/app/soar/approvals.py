"""Approval workflow SOAR (PRD FR-303): approve/deny + timeout + eskalasi.

Aturan Matriks Otonomi §7 no.2:
- **Hanya** sel "timeout → AUTO" (High × K2) yang dieksekusi otomatis saat timeout.
- Sel APPROVAL lain **mengeskalasi** ke approver berikutnya (T2 → T3 → Commander).
- Untuk K1, sistem **tidak pernah** mengeksekusi otomatis.

Enforcement tier: approver harus punya pangkat ≥ `required_tier` approval.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models.soar import (
    ActionExecution,
    ActionStatus,
    Approval,
    ApprovalStatus,
    PlaybookRun,
    RunStatus,
)
from app.soar import autonomy
from app.soar.engine import _execute
from app.soar.notify import notify

# Pangkat approver (pemisahan tugas §7): hanya Commander yang menyetujui.
_TIER_RANK = {"commander": 1}


def can_approve(role: str, required_tier: str) -> bool:
    return _TIER_RANK.get(role, 0) >= _TIER_RANK.get(required_tier, 99)


def _naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _recompute_run(db: Session, run_id: int) -> None:
    aes = db.execute(
        select(ActionExecution).where(ActionExecution.run_id == run_id)
    ).scalars().all()
    run = db.get(PlaybookRun, run_id)
    if run is None:
        return
    if any(a.status == ActionStatus.AWAITING_APPROVAL.value for a in aes):
        run.status = RunStatus.AWAITING_APPROVAL.value
    elif any(a.status == ActionStatus.DENIED.value for a in aes):
        run.status = RunStatus.FAILED.value
    else:
        run.status = RunStatus.COMPLETED.value


def resolve_approval(
    db: Session, approval_id: int, *, approver: str, approver_role: str,
    decision: str, note: str = "", record_audit: bool = True,
) -> Approval:
    """Approve/deny sebuah approval. `decision` ∈ {approve, deny}."""
    ap = db.get(Approval, approval_id)
    if ap is None:
        raise ValueError("Approval tidak ditemukan")
    if ap.status != ApprovalStatus.PENDING.value:
        raise ValueError(f"Approval sudah berstatus {ap.status}")
    if not can_approve(approver_role, ap.required_tier):
        raise PermissionError(f"Butuh pangkat approver '{ap.required_tier}'")

    ae = db.get(ActionExecution, ap.action_execution_id)
    ap.approver = approver
    ap.note = note
    ap.resolved_at = datetime.now(timezone.utc)

    if decision == "approve":
        ap.status = ApprovalStatus.APPROVED.value
        if ae is not None:
            _execute(db, ae, actor=approver)
    elif decision == "deny":
        ap.status = ApprovalStatus.DENIED.value
        if ae is not None:
            ae.status = ActionStatus.DENIED.value
            ae.result = {"denied": True, "by": approver, "note": note}
    else:
        raise ValueError("decision harus 'approve' atau 'deny'")

    if ae is not None:
        _recompute_run(db, ae.run_id)
    if record_audit:
        audit.record(db, action="soar.approval.resolve", actor_type="user", actor_id=approver,
                     object_type="approval", object_id=str(ap.id),
                     payload={"decision": decision, "action": ap.action,
                              "tier": ap.required_tier, "note": note})
    db.commit()
    db.refresh(ap)
    return ap


def process_timeouts(
    db: Session, *, now: datetime | None = None, actor: str = "system",
    record_audit: bool = True,
) -> dict[str, Any]:
    """Proses approval yang melewati deadline (§7 no.2). Dipanggil manual (tanpa scheduler)."""
    now = now or datetime.now(timezone.utc)
    now_n = _naive(now)

    pend = db.execute(
        select(Approval).where(Approval.status == ApprovalStatus.PENDING.value)
    ).scalars().all()

    auto = escalated = expired = 0
    for ap in pend:
        dl = _naive(ap.deadline)
        if dl is None or dl > now_n:
            continue  # belum/ tidak kedaluwarsa

        if ap.on_timeout == "auto":
            # Hanya High × K2 (§7 no.2). Eksekusi otomatis.
            ae = db.get(ActionExecution, ap.action_execution_id)
            if ae is not None:
                _execute(db, ae, actor=actor)
                _recompute_run(db, ae.run_id)
            ap.status = ApprovalStatus.AUTO_TIMEOUT.value
            ap.resolved_at = now
            auto += 1
        else:
            # Eskalasi ke approver berikutnya (T2 → T3 → Commander). K1 tak pernah auto.
            nxt = autonomy.next_approver(ap.required_tier)
            if nxt is not None:
                ap.required_tier = nxt
                ap.deadline = now + timedelta(minutes=10)
                notify(db, recipient_role=nxt, kind="soar_approval_escalated",
                       title=f"Eskalasi approval: {ap.action}",
                       body=f"Timeout approver sebelumnya → eskalasi ke {nxt}.",
                       ref_type="approval", ref_id=ap.id, commit=False)
                escalated += 1
            else:
                ap.status = ApprovalStatus.EXPIRED.value
                ap.resolved_at = now
                notify(db, recipient_role="commander", kind="soar_approval_expired",
                       title=f"Approval kedaluwarsa: {ap.action}",
                       body="Eskalasi mencapai puncak tanpa jawaban. Perlu tindakan manual.",
                       ref_type="approval", ref_id=ap.id, commit=False)
                expired += 1

    if record_audit:
        audit.record(db, action="soar.approval.timeouts", actor_type="system", actor_id=actor,
                     object_type="approval", payload={"auto": auto, "escalated": escalated, "expired": expired})
    db.commit()
    return {"auto": auto, "escalated": escalated, "expired": expired}
