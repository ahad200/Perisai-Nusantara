"""ELANG-1: deteksi anomali jaringan (IsolationForest) + penjelasan fitur (FR-103).

Dilatih dari **baseline historis ≥14 hari** (M3) sehingga mempelajari pola trafik
normal. Entitas yang dianalisis = pasangan (host, tujuan IP). Pola **beaconing C2**
(interval sangat teratur, payload konsisten, berlangsung lama) muncul sebagai
pencilan sehingga diberi skor anomali tinggi.

Setiap alert ML menyertakan **skor** dan **fitur penyebab** (FR-103): fitur dengan
deviasi (z-score) terbesar dari baseline ditandai sebagai kontributor utama.

Gerbang arah (anti false positive): skor IF saja tidak cukup. Dengan data latih
kecil (~55 entitas) entitas normal di pinggir distribusi bisa mencapai skor ~0.66,
sementara IF "jenuh" untuk titik di luar rentang latih sehingga beaconing hanya
~0.67–0.73 — jaraknya terlalu tipis untuk ambang skor. Maka temuan juga wajib
menyimpang **ke arah mencurigakan** (lebih teratur/seragam, atau volume lebih
tinggi) sebesar ≥ ``min_suspicious_z`` sigma. Aktivitas yang *lebih rendah* dari
baseline bukan sinyal C2. Kalibrasi (30 kombinasi seed × durasi baseline):
trafik normal maks ~3.6σ, beaconing min ~10.6σ.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.iforest import IsolationForest
from app.models.event import Event

NETWORK_SOURCES = ("firewall", "proxy")
FEATURE_NAMES = ("count", "interval_cv", "bytes_cv", "span_hours", "active_hours")
# Label fitur yang ramah analis (untuk penjelasan).
FEATURE_LABELS = {
    "count": "jumlah koneksi",
    "interval_cv": "keteraturan interval (CV)",
    "bytes_cv": "keseragaman ukuran (CV)",
    "span_hours": "durasi aktif (jam)",
    "active_hours": "jumlah jam aktif",
}
# Arah deviasi yang mencurigakan per fitur (+1 = lebih tinggi, -1 = lebih rendah).
# Beaconing: interval & ukuran payload sangat teratur (CV rendah); volume tinggi.
SUSPICIOUS_DIRECTION = (+1, -1, -1, +1, +1)


@dataclass(slots=True)
class Entity:
    host: str | None
    dst_ip: str
    events: list[Event]
    vector: list[float]
    first_ts: datetime
    last_ts: datetime


def _cv(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = statistics.fmean(values)
    if m == 0:
        return 0.0
    return statistics.pstdev(values) / m


def _entity_vector(events: list[Event]) -> tuple[list[float], datetime, datetime]:
    evs = sorted(events, key=lambda e: e.ts)
    ts = [e.ts for e in evs]
    intervals = [(ts[i] - ts[i - 1]).total_seconds() for i in range(1, len(ts))]
    byts = [float(e.bytes_out or 0) for e in evs]
    span_hours = (ts[-1] - ts[0]).total_seconds() / 3600 if len(ts) > 1 else 0.0
    active_hours = len({t.replace(minute=0, second=0, microsecond=0) for t in ts})
    vec = [
        float(len(evs)),        # count
        _cv(intervals),         # interval_cv (beaconing -> ~0)
        _cv(byts),              # bytes_cv (beaconing -> ~0)
        span_hours,             # span_hours
        float(active_hours),    # active_hours
    ]
    return vec, ts[0], ts[-1]


def _group_entities(events: list[Event]) -> dict[tuple[str | None, str], Entity]:
    groups: dict[tuple[str | None, str], list[Event]] = {}
    for e in events:
        if e.dst_ip:
            groups.setdefault((e.host, e.dst_ip), []).append(e)
    out: dict[tuple[str | None, str], Entity] = {}
    for (host, dst), evs in groups.items():
        vec, first, last = _entity_vector(evs)
        out[(host, dst)] = Entity(host, dst, evs, vec, first, last)
    return out


def _baseline_stats(vectors: list[list[float]]) -> list[tuple[float, float]]:
    """(mean, stdev) per fitur untuk menghitung z-score penjelasan."""
    stats: list[tuple[float, float]] = []
    for i in range(len(FEATURE_NAMES)):
        col = [v[i] for v in vectors]
        mean = statistics.fmean(col) if col else 0.0
        sd = statistics.pstdev(col) if len(col) > 1 else 0.0
        stats.append((mean, sd))
    return stats


def _explain(vector: list[float], stats: list[tuple[float, float]]) -> list[dict]:
    """Fitur penyebab: urut berdasarkan |z| terhadap baseline (deviasi terbesar dulu)."""
    feats: list[dict] = []
    for i, name in enumerate(FEATURE_NAMES):
        mean, sd = stats[i]
        z = (vector[i] - mean) / sd if sd > 0 else 0.0
        feats.append({
            "name": name, "label": FEATURE_LABELS[name],
            "value": round(vector[i], 3), "baseline_mean": round(mean, 3), "z": round(z, 2),
        })
    feats.sort(key=lambda f: abs(f["z"]), reverse=True)
    return feats


def _suspicious_z(vector: Sequence[float], stats: list[tuple[float, float]]) -> float:
    """Deviasi terbesar (dalam sigma) ke arah mencurigakan; negatif bila tak ada."""
    best = float("-inf")
    for i, direction in enumerate(SUSPICIOUS_DIRECTION):
        mean, sd = stats[i]
        if sd > 0:
            best = max(best, direction * (vector[i] - mean) / sd)
    return best if best != float("-inf") else 0.0


@dataclass(slots=True)
class AnomalyFinding:
    host: str | None
    dst_ip: str
    score: float
    technique: str | None
    technique_name: str | None
    event_ids: list[int]
    first_ts: datetime
    last_ts: datetime
    features: dict


def detect_anomalies(
    db: Session,
    *,
    threshold: float = 0.60,
    min_count: int = 12,
    min_suspicious_z: float = 5.0,
    seed: int = 1337,
) -> list[AnomalyFinding]:
    """Latih dari baseline, skor semua entitas jaringan, kembalikan temuan anomali."""
    net_events = db.execute(
        select(Event).where(Event.source_type.in_(NETWORK_SOURCES))
    ).scalars().all()
    if not net_events:
        return []

    baseline_events = [e for e in net_events if e.scenario == "baseline"]
    baseline_entities = _group_entities(baseline_events)
    if len(baseline_entities) < 4:  # butuh data latih yang cukup
        return []

    train = [e.vector for e in baseline_entities.values()]
    stats = _baseline_stats(train)
    model = IsolationForest(n_trees=120, sample_size=256, seed=seed).fit(train)

    findings: list[AnomalyFinding] = []
    for (host, dst), ent in _group_entities(net_events).items():
        if ent.vector[0] < min_count:  # abaikan entitas kecil/berisik
            continue
        score = model.score(ent.vector)
        if score < threshold:
            continue
        susp_z = _suspicious_z(ent.vector, stats)
        if susp_z < min_suspicious_z:  # pencilan statistik, tapi bukan pola ancaman
            continue
        feats = _explain(ent.vector, stats)
        # Tanda tangan beaconing: payload sangat seragam (ciri terkuat), dengan
        # interval cukup teratur. Tahan terhadap beberapa gelombang beaconing.
        interval_cv, bytes_cv = ent.vector[1], ent.vector[2]
        is_beaconing = bytes_cv < 0.15 and interval_cv < 1.0
        tech = ("T1071", "Application Layer Protocol") if is_beaconing else (None, None)
        findings.append(AnomalyFinding(
            host=host, dst_ip=dst, score=round(score, 4),
            technique=tech[0], technique_name=tech[1],
            event_ids=[e.id for e in ent.events][:200],
            first_ts=ent.first_ts, last_ts=ent.last_ts,
            features={
                "score": round(score, 4),
                "dst_ip": dst,
                "features": feats,
                "top": [f["name"] for f in feats[:3]],
                "suspicious_z": round(susp_z, 2),
                "model": "IsolationForest (ELANG-1)",
            },
        ))
    return findings
