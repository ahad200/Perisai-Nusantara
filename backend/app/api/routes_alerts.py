"""Router antrian alert + triase (PRD M5, Lampiran C "Antrian Alert")."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app import audit
from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.alert import Alert, AlertStatus
from app.models.asset import Asset
from app.models.detection import SEVERITY_RANK
from app.models.event import Event
from app.models.user import User
from app.schemas.detection import (
    AlertDetailOut,
    AlertOut,
    AlertPage,
    AssignRequest,
    CloseRequest,
)
from app.schemas.event import EventOut

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Ekspresi urutan severity (critical dulu) untuk antrian.
_SEV_ORDER = case(
    *[(Alert.severity == sev, rank) for sev, rank in SEVERITY_RANK.items()],
    else_=0,
)


def _filters(stmt, *, severity, status_, technique, assignee, asset_id):
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if status_:
        stmt = stmt.where(Alert.status == status_)
    if technique:
        stmt = stmt.where(Alert.technique == technique)
    if assignee:
        stmt = stmt.where(Alert.assignee == assignee)
    if asset_id is not None:
        stmt = stmt.where(Alert.asset_id == asset_id)
    return stmt


@router.get("", response_model=AlertPage)
def list_alerts(
    _: User = Depends(require_permission(Permission.ALERT_READ)),
    db: Session = Depends(get_db),
    severity: str | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    technique: str | None = Query(default=None),
    assignee: str | None = Query(default=None),
    asset_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> AlertPage:
    f = dict(severity=severity, status_=status_, technique=technique,
             assignee=assignee, asset_id=asset_id)
    total = db.execute(_filters(select(func.count(Alert.id)), **f)).scalar_one()
    stmt = (
        _filters(select(Alert, Asset.criticality).outerjoin(Asset, Alert.asset_id == Asset.id), **f)
        .order_by(_SEV_ORDER.desc(), Alert.last_event_ts.desc(), Alert.id.desc())
        .offset(offset).limit(limit)
    )
    items: list[AlertOut] = []
    for alert, crit in db.execute(stmt).all():
        out = AlertOut.model_validate(alert)
        out.asset_criticality = crit
        items.append(out)
    return AlertPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{alert_id}", response_model=AlertDetailOut)
def get_alert(
    alert_id: int,
    _: User = Depends(require_permission(Permission.ALERT_READ)),
    db: Session = Depends(get_db),
) -> AlertDetailOut:
    row = db.execute(
        select(Alert, Asset.criticality).outerjoin(Asset, Alert.asset_id == Asset.id)
        .where(Alert.id == alert_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert tidak ditemukan")
    alert, crit = row
    out = AlertDetailOut.model_validate(alert)
    out.asset_criticality = crit
    # Event penyebab (maksimal 200 agar respons tetap ringan).
    ids = (alert.event_ids or [])[:200]
    events = db.execute(select(Event).where(Event.id.in_(ids)).order_by(Event.ts.asc())).scalars().all()
    out.events = [EventOut.model_validate(e) for e in events]
    return out


def _get(db: Session, alert_id: int) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert tidak ditemukan")
    return alert


def _audit(db, actor, alert, action, payload):
    audit.record(db, action=action, actor_type="user", actor_id=actor.username,
                 object_type="alert", object_id=str(alert.id), payload=payload)


@router.post("/{alert_id}/assign", response_model=AlertOut)
def assign_alert(
    alert_id: int,
    body: AssignRequest,
    actor: User = Depends(require_permission(Permission.ALERT_TRIAGE)),
    db: Session = Depends(get_db),
) -> Alert:
    alert = _get(db, alert_id)
    alert.assignee = body.assignee or actor.username
    alert.status = AlertStatus.ASSIGNED.value
    db.commit()
    db.refresh(alert)
    _audit(db, actor, alert, "alert.assign", {"assignee": alert.assignee})
    return alert


@router.post("/{alert_id}/escalate", response_model=AlertOut)
def escalate_alert(
    alert_id: int,
    actor: User = Depends(require_permission(Permission.ALERT_TRIAGE)),
    db: Session = Depends(get_db),
) -> Alert:
    alert = _get(db, alert_id)
    alert.status = AlertStatus.ESCALATED.value
    db.commit()
    db.refresh(alert)
    _audit(db, actor, alert, "alert.escalate", {"by": actor.username, "role": actor.role})
    return alert


@router.post("/{alert_id}/close", response_model=AlertOut)
def close_alert(
    alert_id: int,
    body: CloseRequest,
    actor: User = Depends(require_permission(Permission.ALERT_TRIAGE)),
    db: Session = Depends(get_db),
) -> Alert:
    alert = _get(db, alert_id)
    alert.status = (
        AlertStatus.CLOSED_FP.value if body.reason == "fp" else AlertStatus.CLOSED_RESOLVED.value
    )
    db.commit()
    db.refresh(alert)
    _audit(db, actor, alert, "alert.close", {"reason": body.reason})
    return alert
