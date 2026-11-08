"""Model AuditEntry — audit log immutable berbasis hash chain (PRD §12, FR-602).

Pemetaan ke PRD §12:
  id, timestamp(ts), aktor(actor_type/actor_id), aksi(action),
  objek(object_type/object_id), payload_hash, prev_hash, hash(entry_hash).

Entri audit **tidak pernah** di-update atau dihapus. Integritas dijamin dengan
merantai `prev_hash` -> `entry_hash` (lihat app/audit/service.py).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Hash entri "genesis" (pendahulu entri pertama). 64 nol heksадesimal.
GENESIS_HASH = "0" * 64


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    # id berfungsi sebagai nomor urut rantai (monotonik).
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)  # user|agent|system
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditEntry id={self.id} action={self.action} hash={self.entry_hash[:8]}…>"
