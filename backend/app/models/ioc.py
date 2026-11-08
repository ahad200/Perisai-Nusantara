"""Model IoC + siklus hidup (PRD §12, FR-201/205).

Atribut PRD §12: id, tipe, nilai, sumber, TLP, confidence, first_seen, expires_at.
Ditambah `status` siklus hidup (aktif/kedaluwarsa/whitelist/false-positive) dan
`stix_id` agar impor STIX idempotent.

Aturan FR-205: IoC yang **kedaluwarsa / whitelist / false-positive tidak lagi
dipakai untuk blokir**. Lihat `is_blockable` / `effective_status`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IoCType(StrEnum):
    IP = "ip"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    URL = "url"
    EMAIL = "email"
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    OTHER = "other"


class Tlp(StrEnum):
    WHITE = "WHITE"
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


class IoCStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    WHITELISTED = "whitelisted"
    FALSE_POSITIVE = "false_positive"


def utcnow_naive() -> datetime:
    """UTC naif — konsisten lintas SQLite/Postgres (hindari campur naive/aware)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class IoC(Base):
    __tablename__ = "iocs"
    __table_args__ = (UniqueConstraint("type", "value", name="uq_iocs_type_value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    tlp: Mapped[str] = mapped_column(String(8), nullable=False, default=Tlp.AMBER.value)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=50)  # 0..100
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=IoCStatus.ACTIVE.value, index=True
    )

    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_naive)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_naive)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    stix_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    def effective_status(self, now: datetime | None = None) -> IoCStatus:
        """Status efektif: whitelist/FP mengunci; kedaluwarsa dihitung dari waktu."""
        st = IoCStatus(self.status)
        if st in (IoCStatus.WHITELISTED, IoCStatus.FALSE_POSITIVE):
            return st
        now = as_naive(now) or utcnow_naive()
        exp = as_naive(self.expires_at)
        if exp is not None and exp <= now:
            return IoCStatus.EXPIRED
        return st

    def is_blockable(self, now: datetime | None = None) -> bool:
        """Hanya IoC yang efektif AKTIF boleh dipakai untuk blokir (FR-205)."""
        return self.effective_status(now) is IoCStatus.ACTIVE

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IoC {self.type}:{self.value} {self.status}>"
