"""Router insiden: korelasi + case management (PRD M7)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app import audit
from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.correlation import correlate
from app.models.alert import Alert, AlertStatus
from app.models.detection import SEVERITY_RANK
from app.models.incident import (
    Incident,
    IncidentNote,
    IncidentStatus,
    NoteKind,
    OPEN_INCIDENT_STATUSES,
)
from app.models.user import User
from app.schemas.detection import AlertOut
from app.schemas.incident import (
    AddNoteRequest,
    AssignIncidentRequest,
    CorrelateResult,
    IncidentDetailOut,
    IncidentOut,
    IncidentPage,
    NoteOut,
    StatusRequest,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])

_SEV_ORDER = case(
    *[(Incident.severity == sev, rank) for sev, rank in SEVERITY_RANK.items()],
    else_=0,
)


def _filters(stmt, *, severity, status_, assignee, host, active):
    if severity:
        stmt = stmt.where(Incident.severity == severity)
    if status_:
        stmt = stmt.where(Incident.status == status_)
    if assignee:
        stmt = stmt.where(Incident.assignee == assignee)
    if host:
        stmt = stmt.where(Incident.host == host)
    if active:
        stmt = stmt.where(Incident.status.in_(OPEN_INCIDENT_STATUSES))
    return stmt


def _get(db: Session, incident_id: int) -> Incident:
    inc = db.get(Incident, incident_id)
    if inc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insiden tidak ditemukan")
    return inc


def _audit(db, actor, inc, action, payload):
    audit.record(db, action=action, actor_type="user", actor_id=actor.username,
                 object_type="incident", object_id=str(inc.id), payload=payload)


@router.post("/correlate", response_model=CorrelateResult)
def run_correlation(
    actor: User = Depends(require_permission(Permission.INCIDENT_MANAGE)),
    db: Session = Depends(get_db),
) -> CorrelateResult:
    result = correlate(db, actor_id=actor.username, actor_type="user")
    return CorrelateResult(**result)


@router.get("", response_model=IncidentPage)
def list_incidents(
    _: User = Depends(require_permission(Permission.INCIDENT_READ)),
    db: Session = Depends(get_db),
    severity: str | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    assignee: str | None = Query(default=None),
    host: str | None = Query(default=None),
    active: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> IncidentPage:
    f = dict(severity=severity, status_=status_, assignee=assignee, host=host, active=active)
    total = db.execute(_filters(select(func.count(Incident.id)), **f)).scalar_one()
    stmt = (
        _filters(select(Incident), **f)
        .order_by(_SEV_ORDER.desc(), Incident.last_event_ts.desc(), Incident.id.desc())
        .offset(offset).limit(limit)
    )
    items = [IncidentOut.model_validate(i) for i in db.execute(stmt).scalars().all()]
    return IncidentPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{incident_id}", response_model=IncidentDetailOut)
def get_incident(
    incident_id: int,
    _: User = Depends(require_permission(Permission.INCIDENT_READ)),
    db: Session = Depends(get_db),
) -> IncidentDetailOut:
    inc = _get(db, incident_id)
    out = IncidentDetailOut.model_validate(inc)
    # Alert anggota (FP yang ditutup disembunyikan agar kasus tetap bersih).
    alerts = db.execute(
        select(Alert).where(
            Alert.incident_id == incident_id,
            Alert.status != AlertStatus.CLOSED_FP.value,
        ).order_by(Alert.first_event_ts.asc(), Alert.id.asc())
    ).scalars().all()
    out.alerts = [AlertOut.model_validate(a) for a in alerts]
    # Linimasa kasus (terbaru dulu).
    notes = db.execute(
        select(IncidentNote).where(IncidentNote.incident_id == incident_id)
        .order_by(IncidentNote.created_at.desc(), IncidentNote.id.desc())
    ).scalars().all()
    out.notes = [NoteOut.model_validate(n) for n in notes]
    return out


@router.post("/{incident_id}/assign", response_model=IncidentOut)
def assign_incident(
    incident_id: int,
    body: AssignIncidentRequest,
    actor: User = Depends(require_permission(Permission.INCIDENT_MANAGE)),
    db: Session = Depends(get_db),
) -> Incident:
    inc = _get(db, incident_id)
    inc.assignee = body.assignee or actor.username
    db.add(IncidentNote(
        incident_id=inc.id, author=actor.username, kind=NoteKind.ASSIGN.value,
        body=f"Ditugaskan ke {inc.assignee}.",
    ))
    db.commit()
    db.refresh(inc)
    _audit(db, actor, inc, "incident.assign", {"assignee": inc.assignee})
    return inc


@router.post("/{incident_id}/status", response_model=IncidentOut)
def set_status(
    incident_id: int,
    body: StatusRequest,
    actor: User = Depends(require_permission(Permission.INCIDENT_MANAGE)),
    db: Session = Depends(get_db),
) -> Incident:
    inc = _get(db, incident_id)
    old = inc.status
    inc.status = IncidentStatus(body.status).value
    detail = f"Status: {old} -> {inc.status}."
    if body.note:
        detail += f" {body.note}"
    db.add(IncidentNote(
        incident_id=inc.id, author=actor.username, kind=NoteKind.STATUS.value, body=detail,
    ))
    db.commit()
    db.refresh(inc)
    _audit(db, actor, inc, "incident.status", {"from": old, "to": inc.status})
    return inc


@router.post("/{incident_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def add_note(
    incident_id: int,
    body: AddNoteRequest,
    actor: User = Depends(require_permission(Permission.INCIDENT_MANAGE)),
    db: Session = Depends(get_db),
) -> IncidentNote:
    inc = _get(db, incident_id)
    note = IncidentNote(
        incident_id=inc.id, author=actor.username, kind=NoteKind.NOTE.value, body=body.body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    _audit(db, actor, inc, "incident.note", {"note_id": note.id})
    return note
