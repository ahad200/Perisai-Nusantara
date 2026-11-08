"""Skema Audit."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    actor_type: str
    actor_id: str | None
    action: str
    object_type: str | None
    object_id: str | None
    payload_hash: str
    prev_hash: str
    entry_hash: str


class VerifyResponse(BaseModel):
    ok: bool
    count: int
    broken_at: int | None = None
    reason: str | None = None
