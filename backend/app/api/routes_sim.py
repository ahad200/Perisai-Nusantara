"""Router pemicu simulator (data simulasi) — **hanya non-produksi**.

Disediakan agar demo M3 bisa menjalankan skenario dari UI (persona purple team).
Dinonaktifkan total di lingkungan produksi (PRD: adapter nyata = mock, data simulasi).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import audit
from app.api.deps import require_permission
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.user import User
from app.schemas.event import SimRunItem, SimRunRequest, SimRunResponse
from app.simulator.baseline import generate_baseline
from app.simulator.fleet import seed_assets
from app.simulator.scenarios import SCENARIOS, run_all_scenarios

router = APIRouter(prefix="/dev", tags=["dev-simulator"])


def _guard_non_prod() -> None:
    if get_settings().is_prod:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulator dinonaktifkan di produksi",
        )


@router.post("/simulate", response_model=SimRunResponse)
def simulate(
    body: SimRunRequest,
    actor: User = Depends(require_permission(Permission.SIM_RUN)),
    db: Session = Depends(get_db),
) -> SimRunResponse:
    _guard_non_prod()

    # Aset harus ada sebelum event bisa ditautkan.
    created = seed_assets(db)
    results: list[SimRunItem] = []

    if body.scenario == "baseline":
        n = generate_baseline(db, days=body.days)
        results.append(SimRunItem(name="baseline", count=n))
    elif body.scenario == "all":
        n = generate_baseline(db, days=body.days)
        results.append(SimRunItem(name="baseline", count=n))
        for r in run_all_scenarios(db):
            results.append(SimRunItem(name=r.name, technique=r.technique, target=r.target, count=r.count))
    else:
        r = SCENARIOS[body.scenario](db)
        results.append(SimRunItem(name=r.name, technique=r.technique, target=r.target, count=r.count))

    audit.record(
        db,
        action="sim.run",
        actor_type="user",
        actor_id=actor.username,
        object_type="simulator",
        object_id=body.scenario,
        payload={"scenario": body.scenario, "days": body.days,
                 "assets_created": len(created), "total_events": sum(i.count for i in results)},
    )

    return SimRunResponse(ran=body.scenario, assets_created=len(created), results=results)
