"""Skema Incident + case management (PRD §12, M7)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.detection import AlertOut


class TechniqueRef(BaseModel):
    technique: str
    name: str | None = None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_code: str
    title: str
    summary: str
    severity: str
    status: str
    assignee: str | None
    asset_id: int | None
    host: str | None
    techniques: list[TechniqueRef] = []
    alert_count: int
    first_event_ts: datetime | None
    last_event_ts: datetime | None
    created_at: datetime
    updated_at: datetime


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author: str
    kind: str
    body: str
    created_at: datetime


class IncidentDetailOut(IncidentOut):
    alerts: list[AlertOut] = []
    notes: list[NoteOut] = []


class IncidentPage(BaseModel):
    items: list[IncidentOut]
    total: int
    limit: int
    offset: int


class CorrelateResult(BaseModel):
    incidents: int
    created: int
    updated: int
    alerts_correlated: int


class AssignIncidentRequest(BaseModel):
    assignee: str | None = None  # kosong = assign ke diri sendiri


class StatusRequest(BaseModel):
    status: Literal["open", "investigating", "contained", "closed"]
    note: str | None = None


class AddNoteRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2048)
