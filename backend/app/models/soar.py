"""Model SOAR (PRD §12, M8): Playbook, PlaybookRun, ActionExecution, Approval,
Notification, BreakGlass.

Prinsip inti (PRD §A.5):
- no.1: agen LLM tak boleh memanggil adapter langsung — hanya `app/soar/` yang boleh.
- no.2: keputusan auto/approval lewat Matriks Otonomi (konfigurasi, bukan hardcode).
- no.3: setiap aksi/approval/rollback menulis AuditEntry.
- no.8: semua adapter mock (hanya mencatat aksi).

`ActionExecution` adalah satu langkah playbook yang dieksekusi/ditunda; menyimpan
`reversible` + `rolled_back` untuk mendukung rollback (FR-304). `Approval`
mengikuti alur approval + timeout + eskalasi (FR-303).
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.asset import _utcnow


class PlaybookStatus(StrEnum):
    ACTIVE = "active"      # disetujui CAB, boleh dieksekusi
    DRAFT = "draft"        # draf (mis. dari generator) — tak boleh auto-eksekusi


class RunMode(StrEnum):
    AUTO = "auto"          # jalankan sesuai Matriks Otonomi
    DRY_RUN = "dry_run"    # simulasi, tanpa efek nyata (FR-306)


class RunStatus(StrEnum):
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ActionStatus(StrEnum):
    EXECUTED = "executed"
    AWAITING_APPROVAL = "awaiting_approval"
    DENIED = "denied"
    SKIPPED = "skipped"
    SIMULATED = "simulated"      # dry-run
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"      # timeout -> approver berikutnya
    AUTO_TIMEOUT = "auto_timeout"  # timeout -> AUTO (hanya High × K2)
    EXPIRED = "expired"          # eskalasi habis tanpa jawaban


class Playbook(Base):
    __tablename__ = "playbooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    trigger_technique: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    # Langkah: list[{action, params, disruptive, pre_approved}]
    steps: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=PlaybookStatus.ACTIVE.value)
    owner: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class PlaybookRun(Base):
    __tablename__ = "playbook_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    playbook_id: Mapped[int | None] = mapped_column(
        ForeignKey("playbooks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    playbook_code: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default=RunMode.AUTO.value)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=RunStatus.RUNNING.value, index=True
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    criticality: Mapped[str] = mapped_column(String(2), nullable=False, default="")
    host: Mapped[str | None] = mapped_column(String(128), nullable=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class ActionExecution(Base):
    __tablename__ = "action_executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("playbook_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    disruptive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pre_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    decision_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="")  # auto/approval
    decision_reason: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    # Muat "awaiting_approval" (17) — String(16) terlalu pendek di Postgres.
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=ActionStatus.SKIPPED.value)
    rolled_back: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    action_execution_id: Mapped[int] = mapped_column(
        ForeignKey("action_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    criticality: Mapped[str] = mapped_column(String(2), nullable=False, default="")

    required_tier: Mapped[str] = mapped_column(String(16), nullable=False)  # role minimal approver
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ApprovalStatus.PENDING.value, index=True
    )
    on_timeout: Mapped[str] = mapped_column(String(16), nullable=False, default="escalate")
    approver: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="info")
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    body: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class BreakGlass(Base):
    """Mode darurat (PRD §7 no.3): Commander menurunkan ambang approval sementara."""
    __tablename__ = "break_glass"

    id: Mapped[int] = mapped_column(primary_key=True)
    activated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
