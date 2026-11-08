"""Skema IoC, enrichment, impor STIX (PRD §12, M4)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.ioc import IoCStatus, IoCType, Tlp


class IoCCreate(BaseModel):
    type: IoCType
    value: str = Field(min_length=1, max_length=512)
    source: str = Field(default="manual", max_length=128)
    tlp: Tlp = Tlp.AMBER
    confidence: int = Field(default=50, ge=0, le=100)
    expires_at: datetime | None = None
    description: str = Field(default="", max_length=512)
    tags: list[str] = Field(default_factory=list)


class IoCOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    value: str
    source: str
    tlp: str
    confidence: int
    status: str
    effective_status: str
    blockable: bool
    first_seen: datetime
    last_seen: datetime
    expires_at: datetime | None
    description: str
    tags: list[str]
    stix_id: str | None


class EnrichmentOut(BaseModel):
    kind: str
    source: str
    data: dict[str, Any]
    mirror_updated_at: datetime
    mirror_age_days: int


class IoCDetailOut(IoCOut):
    enrichment: list[EnrichmentOut]


class IoCPage(BaseModel):
    items: list[IoCOut]
    total: int
    limit: int
    offset: int


class IoCStatusUpdate(BaseModel):
    status: IoCStatus


class StixImportRequest(BaseModel):
    bundle: dict[str, Any]
    source: str = Field(default="STIX import", max_length=128)


class StixImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    total_indicators: int
    errors: list[str]
