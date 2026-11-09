"""Model Incident + IncidentNote (PRD §12, M7 — korelasi & case management).

Sebuah **Insiden** mengelompokkan beberapa Alert terkait (M5) menjadi satu kasus
yang dikelola lewat siklus respons (NIST SP 800-61 disederhanakan):

    open -> investigating -> contained -> closed

Korelasi mengelompokkan alert berdasarkan **entitas utama** (host/aset): beberapa
alert pada host yang sama menyusun satu narasi rantai serangan (mis. brute force
T1110 -> beaconing T1071 -> enkripsi massal T1486). `correlation_key` membuat
korelasi **idempotent** (dijalankan ulang tak menduplikasi insiden).

`IncidentNote` menyimpan **linimasa kasus** (catatan analis + jejak perubahan
status/penugasan). Perubahan state penting tetap ditulis ke audit hash chain
(PRD §A.5 no.3); IncidentNote adalah catatan kerja yang ramah-analis, bukan
pengganti audit.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.asset import _utcnow


class IncidentStatus(StrEnum):
    OPEN = "open"                # baru dibuat korelasi, belum ditangani
    INVESTIGATING = "investigating"
    CONTAINED = "contained"     # penyebaran dihentikan (isolasi aset/akun)
    CLOSED = "closed"


# Status yang dianggap "aktif" (perlu perhatian) untuk papan/antrian insiden.
OPEN_INCIDENT_STATUSES = frozenset(
    {IncidentStatus.OPEN.value, IncidentStatus.INVESTIGATING.value, IncidentStatus.CONTAINED.value}
)


class NoteKind(StrEnum):
    NOTE = "note"        # catatan analis
    STATUS = "status"    # perubahan status siklus hidup
    ASSIGN = "assign"    # penugasan
    SYSTEM = "system"    # dihasilkan korelasi


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    # Kunci korelasi (mis. "host:ws-staff-03") — membuat korelasi idempotent.
    correlation_key: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)

    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    summary: Mapped[str] = mapped_column(String(1024), nullable=False, default="")

    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=IncidentStatus.OPEN.value, index=True
    )
    assignee: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    host: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Agregat didenormalisasi saat korelasi (untuk tampilan & cakupan ATT&CK).
    techniques: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    alert_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    first_event_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Incident {self.incident_code} {self.severity} {self.status} alerts={self.alert_count}>"


class IncidentNote(Base):
    __tablename__ = "incident_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default=NoteKind.NOTE.value)
    body: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IncidentNote inc={self.incident_id} {self.kind} by {self.author}>"
