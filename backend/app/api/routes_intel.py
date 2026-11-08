"""Router threat intel: IoC, enrichment, impor STIX, siklus hidup (PRD M4)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import audit
from app.api.deps import require_permission
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rbac import Permission
from app.intel import expire_stale, import_bundle, lookup_enrichment, set_status
from app.intel.samples import seed_intel
from app.models.ioc import IoC, IoCStatus, utcnow_naive
from app.models.user import User
from app.schemas.ioc import (
    EnrichmentOut,
    IoCCreate,
    IoCDetailOut,
    IoCOut,
    IoCPage,
    IoCStatusUpdate,
    StixImportRequest,
    StixImportResult,
)

router = APIRouter(prefix="/intel", tags=["intel"])


def _to_out(ioc: IoC) -> IoCOut:
    es = ioc.effective_status()
    return IoCOut(
        id=ioc.id, type=ioc.type, value=ioc.value, source=ioc.source, tlp=ioc.tlp,
        confidence=ioc.confidence, status=ioc.status, effective_status=es.value,
        blockable=(es is IoCStatus.ACTIVE), first_seen=ioc.first_seen, last_seen=ioc.last_seen,
        expires_at=ioc.expires_at, description=ioc.description, tags=ioc.tags, stix_id=ioc.stix_id,
    )


@router.get("/iocs", response_model=IoCPage)
def list_iocs(
    _: User = Depends(require_permission(Permission.INTEL_READ)),
    db: Session = Depends(get_db),
    type: str | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    tlp: str | None = Query(default=None),
    source: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> IoCPage:
    # Kedaluwarsa otomatis sebelum menampilkan (FR-205), agar status konsisten.
    expire_stale(db)

    def _filters(stmt):
        if type:
            stmt = stmt.where(IoC.type == type)
        if status_:
            stmt = stmt.where(IoC.status == status_)
        if tlp:
            stmt = stmt.where(IoC.tlp == tlp.upper())
        if source:
            stmt = stmt.where(IoC.source == source)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(IoC.value.ilike(like), IoC.description.ilike(like)))
        return stmt

    total = db.execute(_filters(select(func.count(IoC.id)))).scalar_one()
    rows = db.execute(
        _filters(select(IoC)).order_by(IoC.last_seen.desc(), IoC.id.desc()).offset(offset).limit(limit)
    ).scalars().all()
    return IoCPage(items=[_to_out(i) for i in rows], total=total, limit=limit, offset=offset)


@router.get("/iocs/{ioc_id}", response_model=IoCDetailOut)
def get_ioc(
    ioc_id: int,
    _: User = Depends(require_permission(Permission.INTEL_READ)),
    db: Session = Depends(get_db),
) -> IoCDetailOut:
    ioc = db.get(IoC, ioc_id)
    if ioc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="IoC tidak ditemukan")
    base = _to_out(ioc).model_dump()
    enrichment = [EnrichmentOut(**e) for e in lookup_enrichment(db, ioc.value)]
    return IoCDetailOut(**base, enrichment=enrichment)


@router.post("/iocs", response_model=IoCOut, status_code=status.HTTP_201_CREATED)
def create_ioc(
    body: IoCCreate,
    actor: User = Depends(require_permission(Permission.INTEL_MANAGE)),
    db: Session = Depends(get_db),
) -> IoCOut:
    exists = db.execute(
        select(IoC.id).where(IoC.type == body.type.value, IoC.value == body.value)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="IoC sudah ada")

    now = utcnow_naive()
    exp = body.expires_at.replace(tzinfo=None) if body.expires_at and body.expires_at.tzinfo else body.expires_at
    st = IoCStatus.EXPIRED.value if exp is not None and exp <= now else IoCStatus.ACTIVE.value
    ioc = IoC(
        type=body.type.value, value=body.value, source=body.source, tlp=body.tlp.value,
        confidence=body.confidence, status=st, expires_at=exp,
        description=body.description, tags=body.tags,
    )
    db.add(ioc)
    db.commit()
    db.refresh(ioc)
    audit.record(
        db, action="ioc.create", actor_type="user", actor_id=actor.username,
        object_type="ioc", object_id=str(ioc.id),
        payload={"type": ioc.type, "value": ioc.value, "tlp": ioc.tlp},
    )
    return _to_out(ioc)


@router.post("/iocs/{ioc_id}/status", response_model=IoCOut)
def update_status(
    ioc_id: int,
    body: IoCStatusUpdate,
    actor: User = Depends(require_permission(Permission.INTEL_MANAGE)),
    db: Session = Depends(get_db),
) -> IoCOut:
    ioc = db.get(IoC, ioc_id)
    if ioc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="IoC tidak ditemukan")
    set_status(db, ioc, body.status, actor_id=actor.username)
    return _to_out(ioc)


@router.post("/import/stix", response_model=StixImportResult)
def import_stix(
    body: StixImportRequest,
    actor: User = Depends(require_permission(Permission.INTEL_MANAGE)),
    db: Session = Depends(get_db),
) -> StixImportResult:
    try:
        result = import_bundle(db, body.bundle, default_source=body.source,
                               actor_id=actor.username, actor_type="user")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return StixImportResult(**result)


@router.post("/seed", response_model=StixImportResult)
def seed_sample_intel(
    actor: User = Depends(require_permission(Permission.INTEL_MANAGE)),
    db: Session = Depends(get_db),
) -> StixImportResult:
    """Tanam mirror + impor bundle contoh (demo). Non-produksi."""
    if get_settings().is_prod:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dinonaktifkan di produksi")
    res = seed_intel(db)
    return StixImportResult(
        created=res["created"], updated=res["updated"], skipped=res["skipped"],
        total_indicators=res["total_indicators"], errors=res["errors"],
    )
