"""Router dashboard (PRD §C.3, M9): Situasi (COP), Eksekutif (KPI), Coverage ATT&CK.

Read-only: menghitung metrik deterministik dari data platform (tanpa egress).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.user import User
from app.reports import coverage as coverage_mod
from app.reports import metrics as metrics_mod

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/situasi")
def situasi(
    _: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """Common Operating Picture: postur, insiden aktif, approval tertunda,
    kesehatan sumber data, tren 24 jam, peta segmen."""
    return metrics_mod.situasi_snapshot(db)


@router.get("/executive")
def executive(
    _: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """KPI eksekutif (FR-603): MTTD, MTTR, FP rate, coverage + tren + insiden penting."""
    return metrics_mod.executive_kpis(db, days=days)


@router.get("/coverage")
def coverage(
    _: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    db: Session = Depends(get_db),
) -> dict:
    """Coverage ATT&CK: matriks taktik × teknik prioritas + gap analysis."""
    return coverage_mod.coverage_matrix(db)
