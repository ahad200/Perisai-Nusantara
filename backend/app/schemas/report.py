"""Skema laporan & jadwal (PRD §8.6, M9)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

ReportKindLiteral = Literal["daily", "weekly", "monthly", "incident", "executive", "compliance"]
CadenceLiteral = Literal["daily", "weekly", "monthly"]


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    kind: str
    title: str
    status: str
    summary: str
    period_start: datetime | None
    period_end: datetime | None
    incident_id: int | None
    generated_by: str
    approved_by: str | None
    schedule_id: int | None
    created_at: datetime
    approved_at: datetime | None


class ReportDetailOut(ReportOut):
    data: dict[str, Any]


class GenerateReportRequest(BaseModel):
    kind: ReportKindLiteral
    incident_id: int | None = None


class ReportScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: str
    cadence: str
    enabled: bool
    recipient_role: str
    created_by: str
    last_run_at: datetime | None
    next_run_at: datetime
    created_at: datetime


class ScheduleRequest(BaseModel):
    name: str = ""
    kind: ReportKindLiteral = "daily"
    cadence: CadenceLiteral = "daily"
    recipient_role: str = "commander"
    enabled: bool = True


class RunDueResult(BaseModel):
    ran: int
    reports: list[str]
