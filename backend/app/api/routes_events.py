"""Router penjelajah event (PRD M3: event masuk & bisa difilter)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.asset import Asset
from app.models.event import Event
from app.models.user import User
from app.schemas.event import EventDetailOut, EventOut, EventPage

router = APIRouter(prefix="/events", tags=["events"])


def _apply_filters(stmt, *, source_type, category, scenario, asset_id, host, since, until, q):
    if source_type:
        stmt = stmt.where(Event.source_type == source_type)
    if category:
        stmt = stmt.where(Event.category == category)
    if scenario:
        stmt = stmt.where(Event.scenario == scenario)
    if asset_id is not None:
        stmt = stmt.where(Event.asset_id == asset_id)
    if host:
        stmt = stmt.where(Event.host == host)
    if since:
        stmt = stmt.where(Event.ts >= since)
    if until:
        stmt = stmt.where(Event.ts <= until)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Event.message.ilike(like),
                Event.action.ilike(like),
                Event.host.ilike(like),
                Event.src_ip.ilike(like),
                Event.dst_ip.ilike(like),
                Event.user.ilike(like),
            )
        )
    return stmt


@router.get("", response_model=EventPage)
def list_events(
    _: User = Depends(require_permission(Permission.EVENT_READ)),
    db: Session = Depends(get_db),
    source_type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    scenario: str | None = Query(default=None),
    asset_id: int | None = Query(default=None),
    host: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> EventPage:
    f = dict(
        source_type=source_type, category=category, scenario=scenario,
        asset_id=asset_id, host=host, since=since, until=until, q=q,
    )
    total = db.execute(
        _apply_filters(select(func.count(Event.id)), **f)
    ).scalar_one()

    stmt = _apply_filters(
        select(Event, Asset.criticality).outerjoin(Asset, Event.asset_id == Asset.id), **f
    ).order_by(Event.ts.desc(), Event.id.desc()).offset(offset).limit(limit)

    items: list[EventOut] = []
    for event, crit in db.execute(stmt).all():
        out = EventOut.model_validate(event)
        out.asset_criticality = crit
        items.append(out)

    return EventPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{event_id}", response_model=EventDetailOut)
def get_event(
    event_id: int,
    _: User = Depends(require_permission(Permission.EVENT_READ)),
    db: Session = Depends(get_db),
) -> EventDetailOut:
    row = db.execute(
        select(Event, Asset.criticality)
        .outerjoin(Asset, Event.asset_id == Asset.id)
        .where(Event.id == event_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event tidak ditemukan")
    event, crit = row
    out = EventDetailOut.model_validate(event)
    out.asset_criticality = crit
    return out
