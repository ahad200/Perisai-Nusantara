"""Model AttributionHypothesis (PRD §12, M10).

Atribusi di PN-X adalah **hipotesis dengan confidence**, bukan vonis (PRD §1 no.6,
§4.2: atribusi final otomatis tanpa validasi manusia = out of scope). Dihasilkan
ELANG-3 (Profiler, Sovereign LLM) sebagai usulan; label **Tervalidasi** hanya boleh
diberikan role `ti_officer` (PRD §6).

Setiap hipotesis wajib mencantumkan: aktor, confidence (Rendah/Sedang/Tinggi),
bukti pendukung (merujuk ID event/alert — mitigasi halusinasi §11), dan hipotesis
alternatif (§6 ELANG-3).
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.asset import _utcnow


class Confidence(StrEnum):
    LOW = "low"       # Rendah
    MEDIUM = "medium"  # Sedang
    HIGH = "high"     # Tinggi


class ValidationStatus(StrEnum):
    PROPOSED = "proposed"      # usulan agen, belum ditinjau
    VALIDATED = "validated"    # dibenarkan ti_officer
    REJECTED = "rejected"      # ditolak ti_officer


class AttributionHypothesis(Base):
    __tablename__ = "attribution_hypotheses"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    confidence: Mapped[str] = mapped_column(String(8), nullable=False, default=Confidence.LOW.value)
    # Bukti pendukung: list[{text, refs:[ID event/alert]}] — klaim wajib merujuk ID.
    evidence: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    # Hipotesis alternatif (wajib, §6 ELANG-3).
    alternatives: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    rationale: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    # Indikator prompt-injection yang terdeteksi di data masukan (transparansi §11).
    injection_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ValidationStatus.PROPOSED.value, index=True
    )
    # Agen/model yang membuat (aktor non-manusia) — untuk audit & transparansi.
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="ELANG-3")
    model_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    validator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validator_note: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
