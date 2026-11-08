"""Siklus hidup IoC (PRD FR-205): kedaluwarsa otomatis, whitelist, false-positive."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models.ioc import IoC, IoCStatus, utcnow_naive


def expire_stale(db: Session, *, record_audit: bool = True) -> int:
    """Tandai IoC aktif yang sudah lewat `expires_at` menjadi `expired`.

    IoC kedaluwarsa tidak lagi dipakai untuk blokir (FR-205). Mengembalikan jumlah
    yang diubah.
    """
    now = utcnow_naive()
    stale = (
        db.execute(
            select(IoC).where(
                IoC.status == IoCStatus.ACTIVE.value,
                IoC.expires_at.is_not(None),
                IoC.expires_at <= now,
            )
        )
        .scalars()
        .all()
    )
    for ioc in stale:
        ioc.status = IoCStatus.EXPIRED.value
    db.commit()

    if stale and record_audit:
        audit.record(
            db,
            action="ioc.expire",
            actor_type="system",
            actor_id="scheduler",
            object_type="ioc_batch",
            payload={"count": len(stale), "ids": [i.id for i in stale]},
        )
    return len(stale)


def set_status(
    db: Session,
    ioc: IoC,
    new_status: IoCStatus,
    *,
    actor_id: str,
    actor_type: str = "user",
    record_audit: bool = True,
) -> IoC:
    """Ubah status siklus hidup IoC (whitelist/false-positive/aktifkan kembali)."""
    old = ioc.status
    ioc.status = new_status.value
    ioc.last_seen = utcnow_naive()
    db.commit()
    db.refresh(ioc)

    if record_audit:
        audit.record(
            db,
            action="ioc.status",
            actor_type=actor_type,
            actor_id=actor_id,
            object_type="ioc",
            object_id=str(ioc.id),
            payload={"from": old, "to": new_status.value, "value": ioc.value},
        )
    return ioc
