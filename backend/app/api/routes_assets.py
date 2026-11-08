"""Router inventaris aset (PRD FR-702)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import audit
from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.asset import Asset, resolve_criticality
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetOut

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetOut])
def list_assets(
    _: User = Depends(require_permission(Permission.ASSET_READ)),
    db: Session = Depends(get_db),
    criticality: str | None = Query(default=None),
    segment: str | None = Query(default=None),
    q: str | None = Query(default=None, description="cari hostname/owner/ip"),
) -> list[Asset]:
    stmt = select(Asset).order_by(Asset.criticality.asc(), Asset.hostname.asc())
    if criticality:
        stmt = stmt.where(Asset.criticality == criticality.upper())
    if segment:
        stmt = stmt.where(Asset.segment == segment)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Asset.hostname.ilike(like), Asset.owner.ilike(like), Asset.ip.ilike(like))
        )
    return list(db.execute(stmt).scalars().all())


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def create_asset(
    body: AssetCreate,
    actor: User = Depends(require_permission(Permission.ASSET_MANAGE)),
    db: Session = Depends(get_db),
) -> Asset:
    exists = db.execute(
        select(Asset.id).where(Asset.hostname == body.hostname)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hostname sudah terdaftar")

    # Fail-safe (PRD §A.5 no.6): kritikalitas kosong/tidak valid -> K1.
    crit = resolve_criticality(body.criticality)
    asset = Asset(
        hostname=body.hostname,
        ip=body.ip,
        segment=body.segment,
        owner=body.owner,
        criticality=crit.value,
        tags=body.tags,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    audit.record(
        db,
        action="asset.create",
        actor_type="user",
        actor_id=actor.username,
        object_type="asset",
        object_id=str(asset.id),
        payload={"hostname": asset.hostname, "criticality": asset.criticality},
    )
    return asset


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(
    asset_id: int,
    _: User = Depends(require_permission(Permission.ASSET_READ)),
    db: Session = Depends(get_db),
) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aset tidak ditemukan")
    return asset
