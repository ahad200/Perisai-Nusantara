"""Skema Asset (PRD §12)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset import Criticality


class AssetCreate(BaseModel):
    hostname: str = Field(min_length=1, max_length=128)
    ip: str | None = Field(default=None, max_length=45)
    segment: str = Field(default="", max_length=64)
    owner: str = Field(default="", max_length=128)
    # Opsional: bila kosong/tidak valid -> K1 (fail-safe, diselesaikan di route).
    criticality: Criticality = Criticality.K1
    tags: list[str] = Field(default_factory=list)


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hostname: str
    ip: str | None
    segment: str
    owner: str
    criticality: str
    tags: list[str]
    created_at: datetime
