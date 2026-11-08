"""Router deteksi: aturan + menjalankan mesin deteksi (PRD M5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.detection import run_detection, seed_rules
from app.models.detection import DetectionRule
from app.models.user import User
from app.schemas.detection import DetectionRunResult, RuleOut

router = APIRouter(prefix="/detection", tags=["detection"])


@router.get("/rules", response_model=list[RuleOut])
def list_rules(
    _: User = Depends(require_permission(Permission.ALERT_READ)),
    db: Session = Depends(get_db),
) -> list[DetectionRule]:
    return list(db.execute(select(DetectionRule).order_by(DetectionRule.rule_code)).scalars().all())


@router.post("/rules/seed", response_model=list[RuleOut])
def seed_default_rules(
    _: User = Depends(require_permission(Permission.DETECT_MANAGE)),
    db: Session = Depends(get_db),
) -> list[DetectionRule]:
    seed_rules(db)
    return list(db.execute(select(DetectionRule).order_by(DetectionRule.rule_code)).scalars().all())


@router.post("/run", response_model=DetectionRunResult)
def run(
    actor: User = Depends(require_permission(Permission.DETECT_RUN)),
    db: Session = Depends(get_db),
) -> DetectionRunResult:
    # Pastikan ada aturan (seed otomatis bila kosong agar demo mulus).
    has_rules = db.execute(select(DetectionRule.id).limit(1)).scalar_one_or_none()
    if has_rules is None:
        seed_rules(db)
    result = run_detection(db, actor_id=actor.username, actor_type="user")
    return DetectionRunResult(**result)
