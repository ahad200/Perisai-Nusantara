"""Model Asset (PRD §12: id, hostname, ip, segmen, pemilik, kritikalitas, tags).

Kritikalitas K1/K2/K3 menentukan matriks otonomi respons (PRD §7). Aturan inti
§A.5 no.6: **aset tanpa kritikalitas diperlakukan sebagai K1** (fail-safe) —
lihat `resolve_criticality`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Criticality(StrEnum):
    K1 = "K1"  # Misi-kritis: sistem komando, operasi militer, domain inti
    K2 = "K2"  # Penting: server aplikasi pendukung, administrasi
    K3 = "K3"  # Umum: endpoint pengguna, sistem non-kritis


def resolve_criticality(value: str | Criticality | None) -> Criticality:
    """Fail-safe (PRD §A.5 no.6): nilai kosong/tidak dikenal -> K1 (paling ketat)."""
    if not value:
        return Criticality.K1
    try:
        return Criticality(str(value).upper())
    except ValueError:
        return Criticality.K1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv4/IPv6
    segment: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    owner: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    # Disimpan sebagai string K1/K2/K3; default fail-safe K1.
    criticality: Mapped[str] = mapped_column(
        String(2), nullable=False, default=Criticality.K1.value, index=True
    )
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Asset {self.hostname} {self.criticality}>"
