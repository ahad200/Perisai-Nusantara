"""Coverage ATT&CK (PRD §C.3 "Coverage ATT&CK", metrik Coverage).

Mengukur cakupan deteksi terhadap **teknik prioritas** dari threat model F0
(konfigurasi `priority_techniques.json`), bukan seluruh matriks ATT&CK — 85% dari
seluruh teknik tidak realistis (PRD §1 catatan).

Tingkat deteksi per teknik:
- `none`      : tak ada aturan deteksi aktif untuk teknik ini (→ gap).
- `covered`   : ada ≥1 aturan deteksi aktif, tetapi belum pernah memicu alert.
- `validated` : ada aturan aktif **dan** ≥1 alert nyata (tervalidasi oleh data/BAS).

Coverage% (metrik SM Coverage ATT&CK) = teknik `validated` / total teknik prioritas.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.detection import DetectionRule, RuleStatus

_CONFIG = Path(__file__).with_name("priority_techniques.json")

LEVEL_NONE = "none"
LEVEL_COVERED = "covered"
LEVEL_VALIDATED = "validated"


@lru_cache(maxsize=1)
def _priority_config() -> dict:
    return json.loads(_CONFIG.read_text(encoding="utf-8"))


def priority_technique_ids() -> list[str]:
    cfg = _priority_config()
    return [t["id"] for tac in cfg["tactics"] for t in tac["techniques"]]


def _rule_techniques(db: Session) -> set[str]:
    """Teknik yang punya ≥1 aturan deteksi AKTIF."""
    rows = db.execute(
        select(DetectionRule.technique)
        .where(DetectionRule.status == RuleStatus.ENABLED.value)
        .where(DetectionRule.technique.is_not(None))
    ).all()
    return {r[0] for r in rows if r[0]}


def _alert_techniques(db: Session) -> dict[str, int]:
    """Jumlah alert per teknik (bukti deteksi tervalidasi oleh data)."""
    rows = db.execute(
        select(Alert.technique, func.count(Alert.id))
        .where(Alert.technique.is_not(None))
        .group_by(Alert.technique)
    ).all()
    return {r[0]: int(r[1]) for r in rows if r[0]}


def _level(tech: str, ruled: set[str], alerted: dict[str, int]) -> str:
    has_rule = tech in ruled
    has_alert = alerted.get(tech, 0) > 0
    if has_rule and has_alert:
        return LEVEL_VALIDATED
    if has_rule:
        return LEVEL_COVERED
    return LEVEL_NONE


def coverage_matrix(db: Session) -> dict:
    """Matriks taktik × teknik prioritas dengan tingkat deteksi + analisis gap."""
    cfg = _priority_config()
    ruled = _rule_techniques(db)
    alerted = _alert_techniques(db)

    tactics_out: list[dict] = []
    total = 0
    counts = {LEVEL_NONE: 0, LEVEL_COVERED: 0, LEVEL_VALIDATED: 0}
    gaps: list[dict] = []

    for tac in cfg["tactics"]:
        techs_out = []
        for t in tac["techniques"]:
            lvl = _level(t["id"], ruled, alerted)
            total += 1
            counts[lvl] += 1
            tech_row = {
                "id": t["id"],
                "name": t["name"],
                "level": lvl,
                "alert_count": alerted.get(t["id"], 0),
            }
            techs_out.append(tech_row)
            if lvl == LEVEL_NONE:
                gaps.append({"tactic": tac["name"], "id": t["id"], "name": t["name"]})
        tactics_out.append(
            {
                "id": tac["id"],
                "name": tac["name"],
                "name_id": tac.get("name_id", tac["name"]),
                "techniques": techs_out,
            }
        )

    validated = counts[LEVEL_VALIDATED]
    covered_or_better = counts[LEVEL_VALIDATED] + counts[LEVEL_COVERED]
    return {
        "tactics": tactics_out,
        "total_techniques": total,
        "counts": counts,
        "gaps": gaps,
        # Metrik: coverage tervalidasi (target F1 ≥ 50%, §SM Coverage ATT&CK).
        "coverage_pct": round(100 * validated / total, 1) if total else 0.0,
        "covered_pct": round(100 * covered_or_better / total, 1) if total else 0.0,
    }
