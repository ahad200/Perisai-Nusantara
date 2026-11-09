"""Model pelaporan (PRD §8.6, M9): Report + ReportSchedule.

ELANG-6 (Reporter) di F1 memakai **template deterministik** (bukan LLM). Laporan
ke pihak eksternal **wajib disetujui manusia** sebelum dikirim (PRD §6 catatan,
FR-601/§10): karena itu laporan lahir berstatus `draft` dan harus `approved`.

Isi laporan disimpan sebagai `data` (JSON hasil komputasi deterministik dari
metrik/coverage). PDF dirender on-the-fly dari `data` (lihat `app/reports/pdf.py`),
sehingga tak ada biner yang disimpan di DB.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.asset import _utcnow


class ReportKind(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    INCIDENT = "incident"        # laporan pasca-insiden (FR, §10)
    EXECUTIVE = "executive"      # ringkasan eksekutif (FR-603)
    COMPLIANCE = "compliance"    # kepatuhan (FR-604) — peta kontrol -> bukti


class ReportStatus(StrEnum):
    DRAFT = "draft"              # dihasilkan, menunggu review manusia
    APPROVED = "approved"        # disetujui; boleh dikirim ke pihak eksternal


class ReportCadence(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # Rentang periode laporan (untuk harian/mingguan/bulanan/eksekutif).
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Laporan pasca-insiden merujuk satu insiden.
    incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ReportStatus.DRAFT.value, index=True
    )
    # Hasil komputasi deterministik (section -> konten). Sumber kebenaran render.
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[str] = mapped_column(String(1024), nullable=False, default="")

    generated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportSchedule(Base):
    """Jadwal laporan otomatis (FR-601). Tanpa daemon di prototipe: endpoint
    `run-due` menghasilkan laporan untuk jadwal yang jatuh tempo (`next_run_at <= now`),
    mirip pola `process-timeouts` di SOAR."""
    __tablename__ = "report_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    cadence: Mapped[str] = mapped_column(String(16), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    recipient_role: Mapped[str] = mapped_column(String(32), nullable=False, default="commander")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
