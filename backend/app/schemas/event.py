"""Skema Event & pemicu simulator (PRD §12, M3)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    source_type: str
    host: str | None
    asset_id: int | None
    asset_criticality: str | None = None  # diisi dari join di route
    category: str
    action: str
    outcome: str
    user: str | None
    src_ip: str | None
    dst_ip: str | None
    dst_port: int | None
    bytes_out: int | None
    message: str
    scenario: str | None


class EventDetailOut(EventOut):
    raw: dict[str, Any]


class EventPage(BaseModel):
    """Hasil berhalaman untuk penjelajah event."""
    items: list[EventOut]
    total: int
    limit: int
    offset: int


class SimRunRequest(BaseModel):
    scenario: Literal["baseline", "bruteforce", "beaconing", "ransomware", "all"]
    days: int = Field(default=14, ge=1, le=60)


class SimRunItem(BaseModel):
    name: str
    technique: str | None = None
    target: str | None = None
    count: int


class SimRunResponse(BaseModel):
    ran: str
    assets_created: int
    results: list[SimRunItem]
