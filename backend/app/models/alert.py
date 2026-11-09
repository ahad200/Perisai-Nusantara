"""Model Alert (PRD §12, FR-203).

Atribut PRD §12: id, rule_id, severity, asset_id, event_ids, penjelasan, status,
teknik ATT&CK. Ditambah `assignee`, `dedup_key` (agar deteksi idempotent saat
dijalankan ulang), dan rentang waktu event penyebab.

Status mengikuti alur triase SOC (PRD Lampiran C "Antrian Alert"):
new -> triaged/assigned -> escalated -> closed_fp / closed_resolved.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.asset import _utcnow
from app.models.detection import Severity  # noqa: F401 (re-export konseptual)


class AlertStatus(StrEnum):
    NEW = "new"
    ASSIGNED = "assigned"
    ESCALATED = "escalated"
    CLOSED_FP = "closed_fp"            # false positive
    CLOSED_RESOLVED = "closed_resolved"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("detection_rules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    technique: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    technique_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    host: Mapped[str | None] = mapped_column(String(128), nullable=True)

    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    explanation: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    event_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AlertStatus.NEW.value, index=True
    )
    assignee: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Keanggotaan insiden (M7): diisi oleh mesin korelasi. Null = belum dikorelasi.
    incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Deteksi ML (ELANG-1): skor anomali + fitur penyebab (FR-103). Null untuk alert non-ML.
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Kunci deduplikasi agar menjalankan deteksi berulang tidak menduplikasi alert.
    dedup_key: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)

    first_event_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Alert {self.rule_code} {self.severity} {self.technique} {self.status}>"
