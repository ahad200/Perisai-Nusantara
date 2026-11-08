"""Skenario serangan simulasi (PRD M3). Semua **data simulasi**, defensif.

- brute force          -> MITRE ATT&CK T1110 (Brute Force)
- beaconing C2         -> MITRE ATT&CK T1071 (Application Layer Protocol)
- enkripsi massal      -> MITRE ATT&CK T1486 (Data Encrypted for Impact)

Setiap skenario menghasilkan event mentah lalu menyimpannya lewat `app.ingest`
dengan label `scenario` (ground-truth) agar bisa difilter di UI. Deteksi aktual
(alert + pemetaan ATT&CK) dibangun di M5; di sini hanya pola event-nya.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ingest import ingest_events
from app.ingest.service import RawRecord
from app.simulator.fleet import FLEET


@dataclass(slots=True)
class ScenarioResult:
    name: str
    technique: str
    target: str
    count: int


def _now(end: datetime | None) -> datetime:
    return (end or datetime.now(timezone.utc)).replace(microsecond=0)


def _asset(hostname: str):
    return next(fa for fa in FLEET if fa.hostname == hostname)


def scenario_bruteforce(
    db: Session,
    *,
    target: str = "app-logistik-01",
    attacker_ip: str = "203.0.113.66",
    attempts: int = 60,
    seed: int = 11,
    end: datetime | None = None,
    record_audit: bool = True,
) -> ScenarioResult:
    """T1110: ledakan percobaan login gagal dari satu sumber ke satu host/user."""
    rng = random.Random(seed)
    fa = _asset(target)
    base = _now(end) - timedelta(minutes=attempts)  # berakhir ~sekarang
    users = ["admin", "root", "administrator", "svc_backup", fa.owner.split()[0].lower()]
    records: list[RawRecord] = []
    for i in range(attempts):
        ts = base + timedelta(seconds=i * rng.randint(2, 6))
        records.append(("auth", {
            "host": fa.hostname, "user": rng.choice(users),
            "src_ip": attacker_ip, "event": "login_failed",
        }, ts))
    # Kredensial akhirnya ditemukan (satu keberhasilan di ujung).
    records.append(("auth", {
        "host": fa.hostname, "user": "svc_backup", "src_ip": attacker_ip,
        "event": "login_success",
    }, base + timedelta(minutes=attempts, seconds=5)))

    count = ingest_events(
        db, records, scenario="bruteforce", action="sim.attack.bruteforce",
        record_audit=record_audit,
    )
    return ScenarioResult("bruteforce", "T1110", target, count)


def scenario_beaconing(
    db: Session,
    *,
    target: str = "ws-staff-03",
    c2_ip: str = "198.51.100.23",
    c2_domain: str = "sync-update.example.net",
    duration_hours: int = 4,
    interval_seconds: int = 60,
    seed: int = 22,
    end: datetime | None = None,
    record_audit: bool = True,
) -> ScenarioResult:
    """T1071: beaconing C2 — koneksi keluar berkala ke satu tujuan, byte kecil stabil."""
    rng = random.Random(seed)
    fa = _asset(target)
    total = max(1, (duration_hours * 3600) // interval_seconds)
    start = _now(end) - timedelta(hours=duration_hours)
    records: list[RawRecord] = []
    for i in range(total):
        # Interval nyaris tetap + jitter kecil -> tanda khas beaconing.
        ts = start + timedelta(seconds=i * interval_seconds + rng.randint(-3, 3))
        records.append(("proxy", {
            "host": fa.hostname, "user": fa.owner.split()[0].lower(),
            "dst_domain": c2_domain, "dst_ip": c2_ip, "dst_port": 443,
            "bytes_out": 512 + rng.randint(-24, 24), "method": "POST",
        }, ts))
    count = ingest_events(
        db, records, scenario="beaconing", action="sim.attack.beaconing",
        record_audit=record_audit,
    )
    return ScenarioResult("beaconing", "T1071", target, count)


def scenario_ransomware(
    db: Session,
    *,
    target: str = "ws-staff-05",
    bursts: int = 40,
    seed: int = 33,
    end: datetime | None = None,
    record_audit: bool = True,
) -> ScenarioResult:
    """T1486: enkripsi massal — proses mencurigakan + ledakan modifikasi berkas."""
    rng = random.Random(seed)
    fa = _asset(target)
    start = _now(end) - timedelta(minutes=10)
    records: list[RawRecord] = [
        ("edr", {
            "host": fa.hostname, "user": fa.owner.split()[0].lower(),
            "process": "svch0st.exe", "action": "process_start",
        }, start),
    ]
    for i in range(bursts):
        ts = start + timedelta(seconds=10 + i * rng.randint(1, 4))
        records.append(("edr", {
            "host": fa.hostname, "user": fa.owner.split()[0].lower(),
            "process": "svch0st.exe", "action": "file_encrypt",
            "file_count": rng.randint(80, 400), "op": "encrypt",
        }, ts))
    count = ingest_events(
        db, records, scenario="ransomware", action="sim.attack.ransomware",
        record_audit=record_audit,
    )
    return ScenarioResult("ransomware", "T1486", target, count)


# Registry nama -> fungsi skenario (untuk CLI & endpoint dev).
SCENARIOS = {
    "bruteforce": scenario_bruteforce,
    "beaconing": scenario_beaconing,
    "ransomware": scenario_ransomware,
}


def run_all_scenarios(
    db: Session, *, end: datetime | None = None, record_audit: bool = True
) -> list[ScenarioResult]:
    return [fn(db, end=end, record_audit=record_audit) for fn in SCENARIOS.values()]
