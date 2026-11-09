"""Matriks Otonomi Respons (PRD §7, FR-302).

Keputusan **auto vs approval** dihitung dari dua dimensi — *severity* alert ×
*kritikalitas* aset — dibaca dari **konfigurasi** `autonomy_matrix.json` (PRD §A.5
no.2: konfigurasi, bukan hardcode). Atribut aksi (disruptif / pre-approved) dan
mode **break-glass** (§7 no.3) menyesuaikan sel dasar.

Setiap keputusan membawa **alasan** yang dapat diaudit (FR-302: "dasar keputusan
tercatat").
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.models.asset import Criticality
from app.models.detection import Severity

_MATRIX_PATH = Path(__file__).with_name("autonomy_matrix.json")

# Severity di luar matriks (info) diperlakukan seperti low.
_SEVERITY_ALIAS = {Severity.INFO.value: "low"}


@lru_cache(maxsize=1)
def _matrix() -> dict:
    return json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))


def escalation_chain() -> list[str]:
    return list(_matrix()["escalation_chain"])


def next_approver(current_tier: str) -> str | None:
    chain = escalation_chain()
    if current_tier not in chain:
        return None
    i = chain.index(current_tier)
    return chain[i + 1] if i + 1 < len(chain) else None


@dataclass(slots=True)
class Decision:
    mode: str                       # "auto" | "approval"
    required_tier: str | None = None
    timeout_minutes: int | None = None
    on_timeout: str | None = None   # "auto" | "escalate"
    notify: bool = False
    notify_commander: bool = False
    no_auto: bool = False           # K1: tidak pernah auto walau timeout
    reason: str = ""
    cell_key: str = ""
    inputs: dict = field(default_factory=dict)


def _norm_severity(severity: str) -> str:
    s = str(severity).lower()
    return _SEVERITY_ALIAS.get(s, s)


def decide(
    severity: str,
    criticality: str | Criticality,
    *,
    disruptive: bool = False,
    pre_approved: bool = False,
    break_glass: bool = False,
) -> Decision:
    """Kembalikan keputusan otonomi untuk satu aksi pada satu aset."""
    sev = _norm_severity(severity)
    crit = Criticality(str(criticality).upper()).value if criticality else Criticality.K1.value
    key = f"{sev}|{crit}"
    cells = _matrix()["cells"]
    cell = cells.get(key) or {"mode": "approval", "tier": "commander", "no_auto": True}

    inputs = {
        "severity": sev, "criticality": crit,
        "disruptive": disruptive, "pre_approved": pre_approved, "break_glass": break_glass,
    }

    def _auto(reason: str) -> Decision:
        return Decision(
            mode="auto", notify=bool(cell.get("notify")),
            notify_commander=bool(cell.get("notify_commander")),
            reason=reason, cell_key=key, inputs=inputs,
        )

    def _approval(tier: str, reason: str) -> Decision:
        return Decision(
            mode="approval", required_tier=tier,
            timeout_minutes=cell.get("timeout_minutes"),
            on_timeout=cell.get("on_timeout", "escalate"),
            notify=True, notify_commander=bool(cell.get("notify_commander")),
            no_auto=bool(cell.get("no_auto")), reason=reason, cell_key=key, inputs=inputs,
        )

    base = f"{sev} × {crit}"

    if cell["mode"] == "auto":
        # Sel AUTO. Carve-out Low×K1: hanya aksi non-disruptif yang auto.
        if cell.get("nondisruptive_only") and disruptive:
            tier = cell.get("fallback_tier", "analyst_t3")
            return _approval(tier, f"{base}: aksi disruptif pada aset misi-kritis → approval {tier}.")
        return _auto(f"{base}: eksekusi otomatis sesuai Matriks Otonomi.")

    # Sel APPROVAL.
    # Carve-out Critical×K2: aksi pre-approved CAB → auto segera.
    if cell.get("preapproved_auto") and pre_approved:
        return _auto(f"{base}: aksi pre-approved CAB → auto segera (notifikasi Commander).")

    # Break-glass (§7 no.3): turunkan ambang. K1 tetap butuh approval (Commander).
    if break_glass:
        if crit == Criticality.K1.value:
            return _approval("commander", f"{base}: break-glass aktif, aset K1 tetap butuh approval Commander.")
        d = _auto(f"{base}: break-glass aktif → eksekusi otomatis (ambang approval diturunkan).")
        d.notify = True
        return d

    tier = cell.get("tier", "analyst_t2")
    return _approval(tier, f"{base}: perlu approval {tier} sesuai Matriks Otonomi.")
