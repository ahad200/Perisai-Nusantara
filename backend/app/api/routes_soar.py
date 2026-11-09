"""Router SOAR (PRD M8): playbook, run, approval, notifikasi, break-glass."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.soar import (
    ActionExecution,
    Approval,
    ApprovalStatus,
    BreakGlass,
    Notification,
    Playbook,
    PlaybookRun,
    RunMode,
)
from app.models.user import User
from app.schemas.soar import (
    ActionExecutionOut,
    ApprovalOut,
    BreakGlassOut,
    BreakGlassRequest,
    NotificationOut,
    PlaybookOut,
    ResolveApprovalRequest,
    RunDetailOut,
    RunOut,
    RunRequest,
    RunSummaryResult,
    TimeoutResult,
)
from app.soar import (
    process_timeouts,
    resolve_approval,
    rollback_run,
    run_playbook,
    seed_playbooks,
)
from app.soar.notify import active_break_glass

router = APIRouter(prefix="/soar", tags=["soar"])


# --- Playbooks ---

@router.get("/playbooks", response_model=list[PlaybookOut])
def list_playbooks(
    _: User = Depends(require_permission(Permission.SOAR_READ)),
    db: Session = Depends(get_db),
) -> list[Playbook]:
    return list(db.execute(select(Playbook).order_by(Playbook.code)).scalars().all())


@router.post("/playbooks/seed", response_model=list[PlaybookOut])
def seed(
    _: User = Depends(require_permission(Permission.SOAR_MANAGE)),
    db: Session = Depends(get_db),
) -> list[Playbook]:
    seed_playbooks(db)
    return list(db.execute(select(Playbook).order_by(Playbook.code)).scalars().all())


# --- Runs ---

@router.post("/run", response_model=RunDetailOut)
def run(
    body: RunRequest,
    actor: User = Depends(require_permission(Permission.SOAR_EXECUTE)),
    db: Session = Depends(get_db),
) -> RunDetailOut:
    if not db.execute(select(Playbook.id).limit(1)).scalar_one_or_none():
        seed_playbooks(db)
    try:
        r = run_playbook(db, incident_id=body.incident_id, playbook_code=body.playbook_code,
                         mode=body.mode, actor=actor.username)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _run_detail(db, r.id)


def _run_detail(db: Session, run_id: int) -> RunDetailOut:
    r = db.get(PlaybookRun, run_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run tidak ditemukan")
    out = RunDetailOut.model_validate(r)
    out.actions = [
        ActionExecutionOut.model_validate(a)
        for a in db.execute(
            select(ActionExecution).where(ActionExecution.run_id == run_id)
            .order_by(ActionExecution.step_index.asc())
        ).scalars().all()
    ]
    return out


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    _: User = Depends(require_permission(Permission.SOAR_READ)),
    db: Session = Depends(get_db),
    incident_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[PlaybookRun]:
    stmt = select(PlaybookRun).order_by(PlaybookRun.id.desc()).limit(limit)
    if incident_id is not None:
        stmt = stmt.where(PlaybookRun.incident_id == incident_id)
    return list(db.execute(stmt).scalars().all())


@router.get("/runs/{run_id}", response_model=RunDetailOut)
def get_run(
    run_id: int,
    _: User = Depends(require_permission(Permission.SOAR_READ)),
    db: Session = Depends(get_db),
) -> RunDetailOut:
    return _run_detail(db, run_id)


@router.post("/runs/{run_id}/rollback", response_model=RunSummaryResult)
def rollback(
    run_id: int,
    actor: User = Depends(require_permission(Permission.SOAR_EXECUTE)),
    db: Session = Depends(get_db),
) -> RunSummaryResult:
    try:
        res = rollback_run(db, run_id=run_id, actor=actor.username)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return RunSummaryResult(**res)


# --- Approvals ---

@router.get("/approvals", response_model=list[ApprovalOut])
def list_approvals(
    _: User = Depends(require_permission(Permission.SOAR_READ)),
    db: Session = Depends(get_db),
    status_: str | None = Query(default="pending", alias="status"),
) -> list[Approval]:
    stmt = select(Approval).order_by(Approval.id.desc())
    if status_:
        stmt = stmt.where(Approval.status == status_)
    return list(db.execute(stmt).scalars().all())


@router.post("/approvals/{approval_id}/resolve", response_model=ApprovalOut)
def resolve(
    approval_id: int,
    body: ResolveApprovalRequest,
    actor: User = Depends(require_permission(Permission.SOAR_APPROVE)),
    db: Session = Depends(get_db),
) -> Approval:
    try:
        return resolve_approval(
            db, approval_id, approver=actor.username, approver_role=actor.role,
            decision=body.decision, note=body.note,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/approvals/process-timeouts", response_model=TimeoutResult)
def timeouts(
    actor: User = Depends(require_permission(Permission.SOAR_APPROVE)),
    db: Session = Depends(get_db),
) -> TimeoutResult:
    return TimeoutResult(**process_timeouts(db, actor=actor.username))


# --- Notifications ---

@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    actor: User = Depends(require_permission(Permission.SOAR_READ)),
    db: Session = Depends(get_db),
    unread_only: bool = Query(default=False),
) -> list[Notification]:
    stmt = select(Notification).where(
        Notification.recipient_role == actor.role
    ).order_by(Notification.id.desc()).limit(100)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    return list(db.execute(stmt).scalars().all())


@router.post("/notifications/{notif_id}/read", response_model=NotificationOut)
def mark_read(
    notif_id: int,
    actor: User = Depends(require_permission(Permission.SOAR_READ)),
    db: Session = Depends(get_db),
) -> Notification:
    n = db.get(Notification, notif_id)
    if n is None or n.recipient_role != actor.role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notifikasi tidak ditemukan")
    n.read = True
    db.commit()
    db.refresh(n)
    return n


# --- Break-glass (§7 no.3) ---

@router.get("/break-glass", response_model=BreakGlassOut | None)
def get_break_glass(
    _: User = Depends(require_permission(Permission.SOAR_READ)),
    db: Session = Depends(get_db),
) -> BreakGlass | None:
    return active_break_glass(db)


@router.post("/break-glass", response_model=BreakGlassOut)
def activate_break_glass(
    body: BreakGlassRequest,
    actor: User = Depends(require_permission(Permission.SOAR_MANAGE)),
    db: Session = Depends(get_db),
) -> BreakGlass:
    bg = BreakGlass(
        activated_by=actor.username, reason=body.reason,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=body.minutes),
    )
    db.add(bg)
    db.commit()
    db.refresh(bg)
    audit.record(db, action="soar.break_glass.activate", actor_type="user", actor_id=actor.username,
                 object_type="break_glass", object_id=str(bg.id),
                 payload={"reason": body.reason, "minutes": body.minutes})
    return bg
