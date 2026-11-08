"""Router audit: baca entri & verifikasi integritas hash chain (read-only).

Tidak ada endpoint untuk mengubah/menghapus audit — audit bersifat immutable (FR-602).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit as audit_svc
from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.audit import AuditEntry
from app.models.user import User
from app.schemas.audit import AuditEntryOut, VerifyResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEntryOut])
def list_entries(
    _: User = Depends(require_permission(Permission.AUDIT_READ)),
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[AuditEntry]:
    stmt = select(AuditEntry).order_by(AuditEntry.id.asc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


@router.get("/verify", response_model=VerifyResponse)
def verify(
    _: User = Depends(require_permission(Permission.AUDIT_VERIFY)),
    db: Session = Depends(get_db),
) -> VerifyResponse:
    result = audit_svc.verify_chain(db)
    return VerifyResponse(**result)
