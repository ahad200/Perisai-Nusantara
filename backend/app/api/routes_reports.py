"""Router laporan (PRD §8.6, M9): ELANG-6 Reporter (template) + ekspor PDF + jadwal.

Laporan lahir `draft` dan wajib disetujui manusia sebelum dikirim ke pihak
eksternal (PRD §6/§10). Tak ada endpoint mengubah isi laporan setelah dibuat
(deterministik dari data platform).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.report import Report, ReportSchedule
from app.models.user import User
from app.reports import service as report_svc
from app.schemas.report import (
    GenerateReportRequest,
    ReportDetailOut,
    ReportOut,
    ReportScheduleOut,
    RunDueResult,
    ScheduleRequest,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportOut])
def list_reports(
    _: User = Depends(require_permission(Permission.REPORT_READ)),
    db: Session = Depends(get_db),
    kind: str | None = Query(default=None),
    status_f: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Report]:
    stmt = select(Report).order_by(Report.id.desc())
    if kind:
        stmt = stmt.where(Report.kind == kind)
    if status_f:
        stmt = stmt.where(Report.status == status_f)
    return list(db.execute(stmt.limit(limit)).scalars().all())


@router.post("", response_model=ReportDetailOut, status_code=status.HTTP_201_CREATED)
def generate(
    body: GenerateReportRequest,
    user: User = Depends(require_permission(Permission.REPORT_GENERATE)),
    db: Session = Depends(get_db),
) -> Report:
    try:
        return report_svc.generate_report(
            db, kind=body.kind, incident_id=body.incident_id, actor=user.username
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/schedules", response_model=list[ReportScheduleOut])
def list_schedules(
    _: User = Depends(require_permission(Permission.REPORT_READ)),
    db: Session = Depends(get_db),
) -> list[ReportSchedule]:
    return list(
        db.execute(select(ReportSchedule).order_by(ReportSchedule.id.asc())).scalars().all()
    )


@router.post("/schedules", response_model=ReportScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule(
    body: ScheduleRequest,
    user: User = Depends(require_permission(Permission.REPORT_MANAGE)),
    db: Session = Depends(get_db),
) -> ReportSchedule:
    sch = ReportSchedule(
        name=body.name or f"{body.kind} ({body.cadence})",
        kind=body.kind,
        cadence=body.cadence,
        recipient_role=body.recipient_role,
        enabled=body.enabled,
        created_by=user.username,
    )
    db.add(sch)
    db.commit()
    db.refresh(sch)
    return sch


@router.post("/schedules/run-due", response_model=RunDueResult)
def run_due(
    user: User = Depends(require_permission(Permission.REPORT_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    return report_svc.run_due_schedules(db, actor=user.username)


@router.get("/{report_id}", response_model=ReportDetailOut)
def get_report(
    report_id: int,
    _: User = Depends(require_permission(Permission.REPORT_READ)),
    db: Session = Depends(get_db),
) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="laporan tak ditemukan")
    return report


@router.post("/{report_id}/approve", response_model=ReportDetailOut)
def approve(
    report_id: int,
    user: User = Depends(require_permission(Permission.REPORT_APPROVE)),
    db: Session = Depends(get_db),
) -> Report:
    try:
        return report_svc.approve_report(db, report_id=report_id, approver=user.username)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{report_id}/pdf")
def download_pdf(
    report_id: int,
    _: User = Depends(require_permission(Permission.REPORT_READ)),
    db: Session = Depends(get_db),
) -> Response:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="laporan tak ditemukan")
    pdf_bytes = report_svc.render_report_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{report.code}.pdf"'},
    )
