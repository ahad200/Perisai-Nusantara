"""Test Matriks Otonomi (PRD §7) — WAJIB menguji SEMUA kombinasi
severity × kritikalitas (§A.5 no.7)."""
from __future__ import annotations

import pytest

from app.soar.autonomy import decide, next_approver

# Ekspektasi untuk aksi **disruptif** (bukan pre-approved), tanpa break-glass.
# (mode, required_tier, no_auto, on_timeout) — tier/flag None bila tak relevan.
EXPECTED_DISRUPTIVE = {
    ("low", "K3"): ("auto", None, None, None),
    ("low", "K2"): ("auto", None, None, None),
    ("low", "K1"): ("approval", "analyst_t3", None, "escalate"),   # disruptif pada K1
    ("medium", "K3"): ("auto", None, None, None),
    ("medium", "K2"): ("auto", None, None, None),
    ("medium", "K1"): ("approval", "analyst_t2", False, "escalate"),
    ("high", "K3"): ("auto", None, None, None),
    ("high", "K2"): ("approval", "analyst_t2", False, "auto"),      # timeout → AUTO
    ("high", "K1"): ("approval", "analyst_t3", True, "escalate"),   # tanpa auto
    ("critical", "K3"): ("auto", None, None, None),
    ("critical", "K2"): ("approval", "analyst_t3", False, "escalate"),
    ("critical", "K1"): ("approval", "commander", True, "escalate"),  # tanpa auto
    # info diperlakukan seperti low.
    ("info", "K3"): ("auto", None, None, None),
    ("info", "K2"): ("auto", None, None, None),
    ("info", "K1"): ("approval", "analyst_t3", None, "escalate"),
}


@pytest.mark.parametrize("cell,expected", list(EXPECTED_DISRUPTIVE.items()))
def test_all_combinations_disruptive(cell, expected):
    sev, crit = cell
    d = decide(sev, crit, disruptive=True, pre_approved=False)
    mode, tier, no_auto, on_timeout = expected
    assert d.mode == mode, f"{cell}: mode"
    if mode == "approval":
        assert d.required_tier == tier, f"{cell}: tier"
        assert d.on_timeout == on_timeout, f"{cell}: on_timeout"
        if no_auto is not None:
            assert d.no_auto == no_auto, f"{cell}: no_auto"
    # Dasar keputusan tercatat (FR-302).
    assert d.reason


def test_coverage_is_complete():
    # 5 severity × 3 kritikalitas harus semua ada.
    assert len(EXPECTED_DISRUPTIVE) == 15


# --- Carve-outs ---

def test_low_k1_nondisruptive_is_auto():
    d = decide("low", "K1", disruptive=False)
    assert d.mode == "auto"


def test_critical_k2_preapproved_is_auto():
    d = decide("critical", "K2", disruptive=True, pre_approved=True)
    assert d.mode == "auto" and d.notify_commander


def test_critical_k2_not_preapproved_is_approval():
    d = decide("critical", "K2", disruptive=True, pre_approved=False)
    assert d.mode == "approval"


def test_k1_never_auto_even_critical():
    for sev in ("high", "critical"):
        d = decide(sev, "K1", disruptive=True)
        assert d.mode == "approval" and d.no_auto is True


def test_high_k2_timeout_is_auto():
    d = decide("high", "K2", disruptive=True)
    assert d.on_timeout == "auto" and d.timeout_minutes == 10


# --- Break-glass (§7 no.3) ---

def test_break_glass_downgrades_non_k1_to_auto():
    base = decide("medium", "K1", disruptive=True)
    assert base.mode == "approval"
    d = decide("high", "K2", disruptive=True, break_glass=True)
    assert d.mode == "auto"


def test_break_glass_keeps_k1_approval():
    d = decide("critical", "K1", disruptive=True, break_glass=True)
    assert d.mode == "approval" and d.required_tier == "commander"


# --- Rantai eskalasi ---

def test_escalation_chain():
    assert next_approver("analyst_t2") == "analyst_t3"
    assert next_approver("analyst_t3") == "commander"
    assert next_approver("commander") is None
