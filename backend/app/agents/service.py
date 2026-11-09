"""Layanan agen LLM (M10): ELANG-2 (Hunter), ELANG-3 (Profiler/atribusi),
ELANG-6 (ringkasan insiden). Semua agen MENGUSULKAN, tidak mengeksekusi (§A.5 no.1).

Alur tiap agen (menerapkan kontrol §11):
1. Bangun `AgentContext` terstruktur dari insiden — tiap fakta ber-ID rujukan.
2. Susun prompt; data lapangan dibungkus sebagai tak tepercaya + pindai injection.
3. Panggil Sovereign LLM (default stub offline).
4. Parse → **validasi skema Pydantic** (tolak output kacau).
5. **Grounding**: buang klaim yang merujuk ID mengarang.
6. Simpan/kembalikan + tulis AuditEntry (aktor = agen).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit as audit_svc
from app.agents import grounding
from app.agents.llm import LlmError, get_llm
from app.agents.sandbox import (
    AgentContext,
    ContextItem,
    build_prompt,
    scan_context_injection,
)
from app.agents.schemas import AttributionLLM, HuntLLM, IncidentSummaryLLM
from app.models.alert import Alert
from app.models.attribution import AttributionHypothesis, ValidationStatus
from app.models.event import Event
from app.models.incident import Incident


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_json(raw: str) -> dict:
    """Ekstrak objek JSON dari output LLM (LLM nyata kadang membungkus prosa)."""
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise LlmError("output LLM bukan JSON yang valid")


def _build_context(db: Session, incident_id: int) -> tuple[Incident, AgentContext]:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise ValueError(f"insiden {incident_id} tak ditemukan")

    alerts = (
        db.execute(
            select(Alert).where(Alert.incident_id == incident.id).order_by(Alert.created_at.asc())
        )
        .scalars()
        .all()
    )
    items: list[ContextItem] = []
    event_ids: list[int] = []
    for a in alerts:
        items.append(
            ContextItem(
                ref=f"ALERT-{a.id}",
                text=f"Alert {a.rule_code or a.id} severity {a.severity} teknik {a.technique or '-'}: {a.title}",
                untrusted=a.explanation or "",
                technique=a.technique,
            )
        )
        for eid in (a.event_ids or [])[:2]:
            if eid not in event_ids:
                event_ids.append(eid)

    # Sampel event mentah (tempat teks lapangan tak tepercaya biasanya berada).
    if event_ids:
        events = (
            db.execute(select(Event).where(Event.id.in_(event_ids[:8]))).scalars().all()
        )
        # Petakan event -> teknik via alert yang memuatnya.
        ev_tech: dict[int, str | None] = {}
        for a in alerts:
            for eid in a.event_ids or []:
                ev_tech.setdefault(eid, a.technique)
        for e in events:
            items.append(
                ContextItem(
                    ref=f"EVT-{e.id}",
                    text=f"Event {e.source_type}/{e.action} outcome={e.outcome} host={e.host or '-'}",
                    untrusted=e.message or "",
                    technique=ev_tech.get(e.id),
                )
            )

    techniques = [t.get("technique") if isinstance(t, dict) else t for t in (incident.techniques or [])]
    ctx = AgentContext(
        incident_code=incident.incident_code,
        severity=incident.severity,
        host=incident.host,
        techniques=[t for t in techniques if t],
        items=items,
    )
    return incident, ctx


def _audit(db: Session, *, action: str, actor: str, incident_code: str, payload: dict) -> None:
    audit_svc.record(
        db,
        action=action,
        actor_type="agent",
        actor_id=actor,
        object_type="incident",
        object_id=incident_code,
        payload=payload,
    )


# --------------------------------------------------------------------------- #
# ELANG-3 — hipotesis atribusi                                                #
# --------------------------------------------------------------------------- #
def run_attribution(db: Session, *, incident_id: int, actor: str = "ELANG-3") -> AttributionHypothesis:
    incident, ctx = _build_context(db, incident_id)
    llm = get_llm()
    raw = llm.generate("attribution", build_prompt("Susun hipotesis atribusi.", ctx), ctx)
    parsed = AttributionLLM.model_validate(_parse_json(raw))  # validasi skema

    allowed = ctx.allowed_refs()
    evidence, gflags = grounding.ground_claims(
        [c.model_dump() for c in parsed.evidence], allowed
    )
    flags = scan_context_injection(ctx) + gflags

    hyp = AttributionHypothesis(
        incident_id=incident.id,
        actor=parsed.actor,
        confidence=parsed.confidence,
        evidence=evidence,
        alternatives=parsed.alternatives,
        rationale=parsed.rationale,
        injection_flags=flags,
        status=ValidationStatus.PROPOSED.value,
        created_by="ELANG-3",
        model_name=llm.name,
    )
    db.add(hyp)
    db.commit()
    db.refresh(hyp)
    _audit(
        db,
        action="agent.attribution",
        actor="ELANG-3",
        incident_code=incident.incident_code,
        payload={"hypothesis_id": hyp.id, "confidence": hyp.confidence, "model": llm.name, "injection_flags": flags},
    )
    return hyp


def validate_hypothesis(
    db: Session, *, hypothesis_id: int, validator: str, status: str, note: str = ""
) -> AttributionHypothesis:
    """Label Tervalidasi/Ditolak — hanya role ti_officer (ditegakkan di API)."""
    hyp = db.get(AttributionHypothesis, hypothesis_id)
    if hyp is None:
        raise ValueError(f"hipotesis {hypothesis_id} tak ditemukan")
    status = ValidationStatus(status).value
    hyp.status = status
    hyp.validator = validator
    hyp.validator_note = note[:512]
    hyp.validated_at = _now()
    db.commit()
    db.refresh(hyp)
    _audit(
        db,
        action="agent.attribution.validate",
        actor=validator,
        incident_code=str(hyp.incident_id),
        payload={"hypothesis_id": hyp.id, "status": status},
    )
    return hyp


# --------------------------------------------------------------------------- #
# ELANG-6 — ringkasan insiden (LLM)                                           #
# --------------------------------------------------------------------------- #
def run_summary(db: Session, *, incident_id: int, actor: str = "ELANG-6") -> dict:
    incident, ctx = _build_context(db, incident_id)
    llm = get_llm()
    raw = llm.generate("summary", build_prompt("Ringkas insiden untuk analis.", ctx), ctx)
    parsed = IncidentSummaryLLM.model_validate(_parse_json(raw))

    allowed = ctx.allowed_refs()
    findings, gflags = grounding.ground_claims(
        [c.model_dump() for c in parsed.key_findings], allowed
    )
    flags = scan_context_injection(ctx) + gflags
    _audit(
        db,
        action="agent.summary",
        actor="ELANG-6",
        incident_code=incident.incident_code,
        payload={"model": llm.name, "injection_flags": flags},
    )
    return {
        "incident_code": incident.incident_code,
        "summary": parsed.summary,
        "key_findings": findings,
        "recommended_next_steps": parsed.recommended_next_steps,
        "confidence": parsed.confidence,
        "model": llm.name,
        "injection_flags": flags,
        "draft": True,  # output AI = draf, perlu tinjauan manusia (§11 automation bias)
    }


# --------------------------------------------------------------------------- #
# ELANG-2 — threat hunting                                                    #
# --------------------------------------------------------------------------- #
def run_hunt(db: Session, *, incident_id: int, actor: str = "ELANG-2") -> dict:
    incident, ctx = _build_context(db, incident_id)
    llm = get_llm()
    raw = llm.generate("hunt", build_prompt("Usulkan query threat hunting.", ctx), ctx)
    parsed = HuntLLM.model_validate(_parse_json(raw))

    allowed = ctx.allowed_refs()
    queries = []
    gflags: list[str] = []
    for q in parsed.queries:
        valid, hallu = grounding.filter_refs(q.refs, allowed)
        if hallu:
            gflags.append(f"ref mengarang dibuang: {', '.join(sorted(set(hallu)))}")
        queries.append({"description": q.description, "filter": q.filter, "refs": valid})
    flags = scan_context_injection(ctx) + gflags
    _audit(
        db,
        action="agent.hunt",
        actor="ELANG-2",
        incident_code=incident.incident_code,
        payload={"model": llm.name, "injection_flags": flags},
    )
    return {
        "incident_code": incident.incident_code,
        "hypothesis": parsed.hypothesis,
        "queries": queries,
        "confidence": parsed.confidence,
        "model": llm.name,
        "injection_flags": flags,
        "draft": True,
    }
