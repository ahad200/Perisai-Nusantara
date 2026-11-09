"""Skema output agen LLM (PRD §11 kontrol 3 & §6: output WAJIB sesuai skema JSON
dan divalidasi SEBELUM ditampilkan). Validasi ketat = garis pertahanan terhadap
output LLM yang kacau/terinjeksi.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ConfidenceLiteral = Literal["low", "medium", "high"]


class Claim(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    refs: list[str] = Field(default_factory=list, max_length=20)


class IncidentSummaryLLM(BaseModel):
    """Output ELANG-6 (ringkasan insiden berbantuan LLM)."""
    summary: str = Field(min_length=1, max_length=1200)
    key_findings: list[Claim] = Field(default_factory=list, max_length=12)
    recommended_next_steps: list[str] = Field(default_factory=list, max_length=10)
    confidence: ConfidenceLiteral = "low"


class AttributionLLM(BaseModel):
    """Output ELANG-3 (hipotesis atribusi). Severity TIDAK diambil dari LLM —
    keputusan severity final tetap dari rule engine (§11 kontrol 4)."""
    actor: str = Field(min_length=1, max_length=160)
    confidence: ConfidenceLiteral = "low"
    evidence: list[Claim] = Field(default_factory=list, max_length=12)
    alternatives: list[str] = Field(default_factory=list, max_length=6)
    rationale: str = Field(default="", max_length=1000)


class HuntQuery(BaseModel):
    description: str = Field(min_length=1, max_length=400)
    filter: str = Field(default="", max_length=400)
    refs: list[str] = Field(default_factory=list, max_length=20)


class HuntLLM(BaseModel):
    """Output ELANG-2 (threat hunting berbasis hipotesis)."""
    hypothesis: str = Field(min_length=1, max_length=600)
    queries: list[HuntQuery] = Field(default_factory=list, max_length=10)
    confidence: ConfidenceLiteral = "low"
