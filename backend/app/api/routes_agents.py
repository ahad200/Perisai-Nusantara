"""Router agen LLM (M10, PRD §6/§11): ELANG-2/3/6 + hipotesis atribusi.

Agen hanya MENGUSULKAN (§A.5 no.1). Output sudah divalidasi skema + grounding di
service. Label 'Tervalidasi' hanya role ti_officer (ATTRIBUTION_VALIDATE).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import run_attribution, run_hunt, run_summary, validate_hypothesis
from app.agents.llm import LlmError
from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.attribution import AttributionHypothesis
from app.models.user import User
from app.schemas.agent import (
    AttributionOut,
    HuntOut,
    SummaryOut,
    ValidateRequest,
)

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_call(fn, **kwargs):
    """Bungkus pemanggilan agen: ValueError→404, skema/LLM gagal→422."""
    try:
        return fn(**kwargs)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValidationError, LlmError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"output agen tidak lolos validasi: {exc}",
        ) from exc


@router.post("/incidents/{incident_id}/attribution", response_model=AttributionOut, status_code=status.HTTP_201_CREATED)
def attribution(
    incident_id: int,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db),
) -> AttributionHypothesis:
    return _agent_call(run_attribution, db=db, incident_id=incident_id, actor=user.username)


@router.post("/incidents/{incident_id}/summary", response_model=SummaryOut)
def summary(
    incident_id: int,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db),
) -> dict:
    return _agent_call(run_summary, db=db, incident_id=incident_id, actor=user.username)


@router.post("/incidents/{incident_id}/hunt", response_model=HuntOut)
def hunt(
    incident_id: int,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db),
) -> dict:
    return _agent_call(run_hunt, db=db, incident_id=incident_id, actor=user.username)


@router.get("/attribution", response_model=list[AttributionOut])
def list_attribution(
    _: User = Depends(require_permission(Permission.ATTRIBUTION_READ)),
    db: Session = Depends(get_db),
    incident_id: int | None = Query(default=None),
) -> list[AttributionHypothesis]:
    stmt = select(AttributionHypothesis).order_by(AttributionHypothesis.id.desc())
    if incident_id is not None:
        stmt = stmt.where(AttributionHypothesis.incident_id == incident_id)
    return list(db.execute(stmt).scalars().all())


@router.post("/attribution/{hypothesis_id}/validate", response_model=AttributionOut)
def validate(
    hypothesis_id: int,
    body: ValidateRequest,
    user: User = Depends(require_permission(Permission.ATTRIBUTION_VALIDATE)),
    db: Session = Depends(get_db),
) -> AttributionHypothesis:
    return _agent_call(
        validate_hypothesis,
        db=db,
        hypothesis_id=hypothesis_id,
        validator=user.username,
        status=body.status,
        note=body.note,
    )
