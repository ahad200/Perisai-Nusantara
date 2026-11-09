"""Skema API agen LLM & atribusi (M10)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ClaimOut(BaseModel):
    text: str
    refs: list[str] = []
    grounded: bool = True


class AttributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    actor: str
    confidence: str
    evidence: list[dict]
    alternatives: list[str]
    rationale: str
    injection_flags: list[str]
    status: str
    created_by: str
    model_name: str
    validator: str | None
    validator_note: str
    created_at: datetime
    validated_at: datetime | None


class ValidateRequest(BaseModel):
    status: Literal["validated", "rejected"]
    note: str = ""


class SummaryOut(BaseModel):
    incident_code: str
    summary: str
    key_findings: list[ClaimOut]
    recommended_next_steps: list[str]
    confidence: str
    model: str
    injection_flags: list[str]
    draft: bool


class HuntQueryOut(BaseModel):
    description: str
    filter: str
    refs: list[str] = []


class HuntOut(BaseModel):
    incident_code: str
    hypothesis: str
    queries: list[HuntQueryOut]
    confidence: str
    model: str
    injection_flags: list[str]
    draft: bool
