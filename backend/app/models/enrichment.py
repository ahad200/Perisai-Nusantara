"""Tabel mirror enrichment lokal (PRD FR-202, §A.5 no.5).

Enrichment (WHOIS/GeoIP/reputasi) **hanya** dari mirror lokal yang diperbarui via
transfer satu arah — tidak ada query keluar dari zona air-gapped. `mirror_updated_at`
menyimpan usia data agar bisa ditampilkan (FR-202).
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ioc import utcnow_naive


class EnrichmentKind(StrEnum):
    WHOIS = "whois"
    GEOIP = "geoip"
    REPUTATION = "reputation"


class EnrichmentRecord(Base):
    __tablename__ = "enrichment_mirror"
    __table_args__ = (Index("ix_enrichment_key_kind", "key", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # `key` = nilai yang dicari (IP atau domain). `kind` = jenis enrichment.
    key: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    mirror_updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_naive
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Enrichment {self.kind}:{self.key}>"
