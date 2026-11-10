"""Test ELANG-1: IsolationForest + deteksi anomali beaconing + penjelasan fitur (M6)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.rbac import Role
from app.detection import detect_anomalies, run_detection, seed_rules
from app.detection.anomaly import _suspicious_z
from app.detection.iforest import IsolationForest
from app.models.alert import Alert
from app.simulator import seed_assets
from app.simulator.baseline import generate_baseline
from app.simulator.scenarios import scenario_beaconing

from tests.conftest import bearer, login


# --- IsolationForest ---

def test_iforest_scores_outlier_higher():
    # Klaster normal (Gaussian) padat di tengah; pencilan di ekor jarang (dalam rentang).
    import random as _r
    rng = _r.Random(0)
    normal = [[rng.gauss(0, 1), rng.gauss(0, 1)] for _ in range(400)]
    model = IsolationForest(n_trees=160, sample_size=128, seed=1).fit(normal)
    inlier = model.score([0.0, 0.0])          # pusat (padat)
    outlier = model.score([3.6, 3.6])          # ekor jarang
    assert outlier > inlier  # pencilan diisolasi lebih cepat -> skor lebih tinggi


# --- Deteksi anomali ---

def _prepare(db, days=3):
    seed_assets(db, record_audit=False)
    generate_baseline(db, days=days, seed=5, record_audit=False)
    scenario_beaconing(db, record_audit=False)


def test_beaconing_flagged_as_anomaly_with_features(db_session):
    _prepare(db_session)
    findings = detect_anomalies(db_session)  # default threshold 0.60, min_count 12
    assert findings, "harus ada temuan anomali"
    # Entitas beaconing C2 adalah skor tertinggi.
    top = max(findings, key=lambda f: f.score)
    assert top.dst_ip == "198.51.100.23"
    assert top.host == "ws-staff-03"
    assert top.score >= 0.6
    assert top.technique == "T1071"  # tanda tangan beaconing
    # Penjelasan fitur hadir (FR-103): skor + fitur penyebab.
    assert top.features["score"] == top.score
    assert len(top.features["features"]) == 5
    assert "interval_cv" in {f["name"] for f in top.features["features"]}


def test_normal_baseline_not_overflagged(db_session):
    _prepare(db_session)
    findings = detect_anomalies(db_session)
    # Hanya entitas beaconing C2 yang ditandai — nol FP dari trafik normal.
    assert findings
    assert {(f.host, f.dst_ip) for f in findings} == {("ws-staff-03", "198.51.100.23")}


@pytest.mark.parametrize(
    ("days", "seed"),
    [(3, 2), (3, 4), (3, 5), (14, 1337)],  # (14, 1337) = baseline bawaan CLI/demo
)
def test_clean_baseline_has_no_false_positive(db_session, days, seed):
    # Kasus ini dulu memicu FP: entitas normal "pinggir" skor IF > 0.60 karena data
    # latih kecil (~55 entitas). Baseline murni tanpa serangan wajib nol temuan.
    seed_assets(db_session, record_audit=False)
    generate_baseline(db_session, days=days, seed=seed, record_audit=False)
    assert detect_anomalies(db_session) == []


def test_suspicious_z_ignores_lower_activity():
    stats = [(70.0, 10.0), (1.25, 0.1), (0.8, 0.1), (320.0, 10.0), (60.0, 10.0)]
    # Aktivitas JAUH lebih rendah dari baseline (z sangat negatif pada volume):
    # bukan sinyal ancaman C2 -> skor arah mencurigakan rendah.
    quiet = [20.0, 1.25, 0.8, 200.0, 10.0]
    assert _suspicious_z(quiet, stats) < 1
    # Interval & payload sangat teratur (ciri beaconing) -> z mencurigakan tinggi.
    beacon = [70.0, 0.05, 0.02, 320.0, 60.0]
    assert _suspicious_z(beacon, stats) >= 5
    # Volume jauh lebih tinggi juga mencurigakan.
    burst = [200.0, 1.25, 0.8, 320.0, 60.0]
    assert _suspicious_z(burst, stats) >= 5


def test_finding_exposes_suspicious_z(db_session):
    _prepare(db_session)
    top = max(detect_anomalies(db_session), key=lambda f: f.score)
    assert top.features["suspicious_z"] >= 5


def test_no_baseline_no_training(db_session):
    seed_assets(db_session, record_audit=False)
    scenario_beaconing(db_session, record_audit=False)  # tanpa baseline -> tak bisa latih
    assert detect_anomalies(db_session) == []


# --- Integrasi lewat mesin deteksi ---

def test_run_detection_creates_ml_alert(db_session):
    _prepare(db_session)
    seed_rules(db_session)
    run_detection(db_session, record_audit=False)
    ml = db_session.execute(
        select(Alert).where(Alert.rule_code == "PNX-ELANG1-001")
    ).scalars().all()
    assert len(ml) >= 1
    beacon = next(a for a in ml if a.host == "ws-staff-03")
    assert beacon.technique == "T1071"
    assert beacon.anomaly_score is not None and beacon.anomaly_score >= 0.6
    assert beacon.features is not None and "features" in beacon.features


# --- API ---

def test_ml_alert_detail_exposes_score_and_features(client, make_user, db_session):
    _prepare(db_session)
    make_user("a1", Role.OPERATOR)
    tok = login(client, "a1", "Password123!")["access_token"]

    client.post("/detection/run", headers=bearer(tok))
    page = client.get("/alerts?technique=T1071", headers=bearer(tok)).json()
    ml = [a for a in page["items"] if a["rule_code"] == "PNX-ELANG1-001"]
    assert ml, "alert ELANG-1 harus muncul di antrian"
    assert ml[0]["anomaly_score"] is not None

    detail = client.get(f"/alerts/{ml[0]['id']}", headers=bearer(tok)).json()
    assert detail["features"] is not None
    assert detail["features"]["model"].startswith("IsolationForest")
    assert len(detail["features"]["features"]) == 5
