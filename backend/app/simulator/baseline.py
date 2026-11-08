"""Generator data baseline historis >= 14 hari (PRD M3, FR-103).

Menghasilkan aktivitas "normal" yang **bersih** (tanpa pola serangan) dengan irama
harian (diurnal) mengikuti jam kerja WIB. Dipakai sebagai data latih ELANG-1
(IsolationForest) di M6. Baseline bersih penting untuk mencegah data poisoning
model anomali (PRD §11).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.ingest import ingest_events
from app.ingest.service import RawRecord
from app.models.asset import Criticality
from app.simulator.fleet import FLEET

DEFAULT_BASELINE_DAYS = 14

# Bobot aktivitas per jam WIB (0..23): puncak di jam kerja 08–16.
_DIURNAL = [
    0.05, 0.04, 0.03, 0.03, 0.04, 0.08, 0.20, 0.45,  # 00–07
    0.85, 1.00, 1.00, 0.95, 0.70, 0.95, 1.00, 0.90,  # 08–15
    0.75, 0.50, 0.35, 0.25, 0.20, 0.15, 0.10, 0.07,  # 16–23
]

# Tujuan internal & domain "normal" (mirror lokal — tidak ada egress nyata).
_INTERNAL_DST = ["10.10.1.10", "10.10.2.20", "10.10.2.22", "10.10.5.5", "10.10.5.6"]
_NORMAL_DOMAINS = ["intranet.tni.mil.id", "mail.tni.mil.id", "logistik.tni.mil.id", "repo.local"]

# Perkiraan event/jam pada puncak diurnal, per kritikalitas aset.
_PEAK_RATE = {Criticality.K1: 2.5, Criticality.K2: 3.0, Criticality.K3: 4.0}


def _wib_hour(ts_utc: datetime) -> int:
    return (ts_utc.hour + 7) % 24


def _asset_hour_events(
    rng: random.Random, fa, bucket_start: datetime
) -> list[RawRecord]:
    """Hasilkan event normal untuk satu aset dalam satu jam."""
    weight = _DIURNAL[_wib_hour(bucket_start)]
    lam = _PEAK_RATE[Criticality(fa.criticality)] * weight
    n = _poisson(rng, lam)
    out: list[RawRecord] = []
    for _ in range(n):
        ts = bucket_start + timedelta(seconds=rng.randint(0, 3599))
        roll = rng.random()
        if Criticality(fa.criticality) == Criticality.K3 and roll < 0.45:
            # Endpoint pengguna: login interaktif (kadang typo -> gagal sesekali).
            failed = rng.random() < 0.06
            out.append(("auth", {
                "host": fa.hostname, "user": fa.owner.split()[0].lower(),
                "src_ip": fa.ip, "event": "login_failed" if failed else "login_success",
            }, ts))
        elif roll < 0.72:
            # Trafik jaringan internal (firewall allow).
            out.append(("firewall", {
                "host": fa.hostname, "src_ip": fa.ip,
                "dst_ip": rng.choice(_INTERNAL_DST), "dst_port": rng.choice([443, 445, 3306, 8080]),
                "action": "allow", "bytes": rng.randint(400, 48_000),
            }, ts))
        else:
            # Permintaan web/proxy ke domain internal normal.
            out.append(("proxy", {
                "host": fa.hostname, "user": fa.owner.split()[0].lower(),
                "dst_domain": rng.choice(_NORMAL_DOMAINS), "dst_ip": rng.choice(_INTERNAL_DST),
                "dst_port": 443, "bytes_out": rng.randint(200, 12_000), "method": "GET",
            }, ts))
    return out


def _poisson(rng: random.Random, lam: float) -> int:
    """Sampel Poisson (algoritma Knuth) — menjaga volume event realistis."""
    if lam <= 0:
        return 0
    import math

    limit = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limit:
            return k - 1


def generate_baseline(
    db: Session,
    *,
    days: int = DEFAULT_BASELINE_DAYS,
    seed: int = 1337,
    end: datetime | None = None,
    record_audit: bool = True,
) -> int:
    """Hasilkan & simpan baseline historis. Mengembalikan jumlah event tersimpan."""
    rng = random.Random(seed)
    end = (end or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    total_hours = days * 24
    start = end - timedelta(hours=total_hours)

    records: list[RawRecord] = []
    for h in range(total_hours):
        bucket_start = start + timedelta(hours=h)
        for fa in FLEET:
            records.extend(_asset_hour_events(rng, fa, bucket_start))

    # Jaminan cakupan rentang: pastikan ada event di jam paling awal & paling akhir.
    records.append(("firewall", {
        "host": FLEET[0].hostname, "src_ip": FLEET[0].ip, "dst_ip": _INTERNAL_DST[0],
        "dst_port": 443, "action": "allow", "bytes": 1024,
    }, start + timedelta(seconds=30)))
    records.append(("firewall", {
        "host": FLEET[0].hostname, "src_ip": FLEET[0].ip, "dst_ip": _INTERNAL_DST[0],
        "dst_port": 443, "action": "allow", "bytes": 1024,
    }, end - timedelta(minutes=5)))

    return ingest_events(
        db, records, scenario="baseline", action="sim.baseline", record_audit=record_audit
    )
