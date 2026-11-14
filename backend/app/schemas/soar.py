"""Skema SOAR (PRD §12, M8)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlaybookStep(BaseModel):
    action: str
    params: dict = {}
    disruptive: bool = False
    pre_approved: bool = False


class PlaybookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    version: int
    trigger_technique: str | None
    status: str
    owner: str
    description: str
    steps: list[PlaybookStep] = []


class ActionExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    step_index: int
    action: str
    params: dict
    disruptive: bool
    pre_approved: bool
    reversible: bool
    decision_mode: str
    decision_reason: str
    status: str
    rolled_back: bool
    result: dict | None = None
    approval_id: int | None = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    playbook_code: str
    incident_id: int | None
    mode: str
    status: str
    severity: str
    criticality: str
    host: str | None
    actor: str
    summary: dict
    created_at: datetime


class RunDetailOut(RunOut):
    actions: list[ActionExecutionOut] = []


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_execution_id: int
    run_id: int
    incident_id: int | None
    action: str
    severity: str
    criticality: str
    required_tier: str
    host: str | None = None
    status: str
    on_timeout: str
    approver: str | None
    note: str
    requested_at: datetime
    deadline: datetime | None
    resolved_at: datetime | None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient_role: str
    kind: str
    title: str
    body: str
    ref_type: str | None
    ref_id: int | None
    read: bool
    created_at: datetime


class RunRequest(BaseModel):
    incident_id: int
    playbook_code: str | None = None
    mode: Literal["auto", "dry_run"] = "auto"


class ResolveApprovalRequest(BaseModel):
    decision: Literal["approve", "deny"]
    note: str = Field(default="", max_length=512)
    # Wajib untuk approve aset K1: nama aset diketik ulang (PRD Lampiran C).
    confirm_host: str = Field(default="", max_length=255)


class BreakGlassRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)
    minutes: int = Field(default=30, ge=1, le=240)


class BreakGlassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activated_by: str
    reason: str
    activated_at: datetime
    expires_at: datetime


class RunSummaryResult(BaseModel):
    run_id: int
    rolled_back: int
    skipped: int
    status: str


class TimeoutResult(BaseModel):
    auto: int
    escalated: int
    expired: int
