"""Model Event (PRD §12: id, timestamp, source_type, asset_id, data ternormalisasi, raw).

Event disimpan dalam skema **ternormalisasi** (mirip ECS/OCSF) hasil `app/ingest/`.
`raw` menyimpan muatan sumber asli (data simulasi). `scenario` menandai asal
skenario simulator (baseline/bruteforce/beaconing/ransomware) untuk penyaringan &
demo — ini label ground-truth simulator, bukan hasil deteksi (deteksi ada di M5).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Host asal (dari log). asset_id terisi bila host cocok dengan inventaris.
    host: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Field ternormalisasi (ECS/OCSF-inspired).
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # authentication|network|file|process|other
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")  # success|failure|unknown
    user: Mapped[str | None] = mapped_column(String(128), nullable=True)

    src_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    dst_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    dst_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_out: Mapped[int | None] = mapped_column(Integer, nullable=True)

    message: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    scenario: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    raw: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Event id={self.id} {self.source_type}/{self.action} host={self.host}>"
