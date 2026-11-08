"""Skema DetectionRule & Alert (PRD §12, M5)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.event import EventOut


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_code: str
    name: str
    type: str
    severity: str
    technique: str | None
    technique_name: str | None
    status: str
    version: int
    description: str


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_code: str
    severity: str
    technique: str | None
    technique_name: str | None
    asset_id: int | None
    asset_criticality: str | None = None
    host: str | None
    title: str
    explanation: str
    event_count: int
    status: str
    assignee: str | None
    anomaly_score: float | None = None
    first_event_ts: datetime | None
    last_event_ts: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertDetailOut(AlertOut):
    event_ids: list[int] = []
    events: list[EventOut] = []
    features: dict | None = None


class AlertPage(BaseModel):
    items: list[AlertOut]
    total: int
    limit: int
    offset: int


class AssignRequest(BaseModel):
    assignee: str | None = None  # kosong = assign ke diri sendiri


class CloseRequest(BaseModel):
    reason: Literal["fp", "resolved"] = "fp"


class DetectionRunResult(BaseModel):
    rules_run: int
    candidates: int
    created: int
    updated: int
