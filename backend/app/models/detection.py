"""Model DetectionRule (PRD §12, FR-102/203).

Atribut PRD §12: id, tipe (sigma/yara/ml), konten, versi, teknik ATT&CK, status.
Setiap aturan membawa **tag teknik MITRE ATT&CK** (FR-203). `content` (JSON)
menyimpan definisi aturan sesuai `type`:

- `sigma`     : {"selection": {field: value|[values]}, ...}  (kecocokan field)
- `threshold` : {"filter": {...}, "group_by": [fields], "count": N, "window_seconds": S}
- `ioc`       : dibangkitkan dari IoC aktif (M4); content kosong.

(yara/ml adalah placeholder untuk milestone berikutnya — ml = ELANG-1 di M6.)
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.asset import _utcnow


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Urutan severity untuk pengurutan antrian (makin tinggi makin atas).
SEVERITY_RANK: dict[str, int] = {
    Severity.CRITICAL.value: 4,
    Severity.HIGH.value: 3,
    Severity.MEDIUM.value: 2,
    Severity.LOW.value: 1,
    Severity.INFO.value: 0,
}


class RuleType(StrEnum):
    SIGMA = "sigma"
    THRESHOLD = "threshold"
    IOC = "ioc"
    YARA = "yara"
    ML = "ml"


class RuleStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class DetectionRule(Base):
    __tablename__ = "detection_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False, default=RuleType.SIGMA.value)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default=Severity.MEDIUM.value)
    technique: Mapped[str | None] = mapped_column(String(16), nullable=True)  # mis. T1110
    technique_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=RuleStatus.ENABLED.value)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DetectionRule {self.rule_code} {self.type} {self.technique}>"
