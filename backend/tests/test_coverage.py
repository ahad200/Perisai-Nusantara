"""Test coverage ATT&CK terhadap teknik prioritas (M9)."""
from __future__ import annotations

from app.detection import run_detection, seed_rules
from app.intel.samples import seed_intel
from app.reports import coverage as cov
from app.simulator import run_all_scenarios, seed_assets


def _prepare(db):
    seed_assets(db, record_audit=False)
    run_all_scenarios(db, record_audit=False)
    seed_intel(db, record_audit=False)
    seed_rules(db)
    run_detection(db, record_audit=False)


def test_priority_techniques_loaded():
    ids = cov.priority_technique_ids()
    # Teknik inti skenario harus ada di daftar prioritas.
    for t in ("T1110", "T1486", "T1071", "T1036", "T1595"):
        assert t in ids


def test_matrix_structure_and_levels(db_session):
    _prepare(db_session)
    m = cov.coverage_matrix(db_session)
    assert m["total_techniques"] == len(cov.priority_technique_ids())
    # Setiap teknik punya level yang valid.
    levels = {
        t["id"]: t["level"]
        for tac in m["tactics"]
        for t in tac["techniques"]
    }
    assert set(levels.values()) <= {"none", "covered", "validated"}
    # Teknik dengan aturan + alert nyata → validated.
    assert levels["T1110"] == "validated"
    assert levels["T1486"] == "validated"


def test_gaps_are_techniques_without_rules(db_session):
    _prepare(db_session)
    m = cov.coverage_matrix(db_session)
    gap_ids = {g["id"] for g in m["gaps"]}
    # Teknik prioritas tanpa aturan deteksi (mis. T1190 exploit) jadi gap.
    assert "T1190" in gap_ids
    # Yang tervalidasi tak boleh muncul di gap.
    assert "T1110" not in gap_ids


def test_coverage_pct_counts_validated(db_session):
    _prepare(db_session)
    m = cov.coverage_matrix(db_session)
    total = m["total_techniques"]
    validated = m["counts"]["validated"]
    assert m["coverage_pct"] == round(100 * validated / total, 1)
    assert m["coverage_pct"] > 0


def test_empty_db_zero_coverage(db_session):
    m = cov.coverage_matrix(db_session)
    assert m["coverage_pct"] == 0.0
    assert m["counts"]["validated"] == 0
    assert len(m["gaps"]) == m["total_techniques"]
