"""Simulator log & skenario serangan (PRD M3) — **data simulasi** sepenuhnya.

Isi:
- `fleet`      : armada aset contoh (K1/K2/K3) + penanaman ke DB.
- `baseline`   : generator data historis "bersih" >= 14 hari (untuk ELANG-1 / M6).
- `scenarios`  : skenario serangan brute force (T1110), beaconing C2 (T1071),
                 enkripsi massal/ransomware (T1486).

Semua event masuk lewat `app.ingest` sehingga ternormalisasi & tertaut ke aset.
Tidak ada trafik jaringan nyata; murni menghasilkan baris log tiruan.
"""
from app.simulator.baseline import generate_baseline
from app.simulator.fleet import FLEET, seed_assets
from app.simulator.scenarios import (
    SCENARIOS,
    run_all_scenarios,
    scenario_beaconing,
    scenario_bruteforce,
    scenario_ransomware,
)

__all__ = [
    "FLEET",
    "seed_assets",
    "generate_baseline",
    "SCENARIOS",
    "scenario_bruteforce",
    "scenario_beaconing",
    "scenario_ransomware",
    "run_all_scenarios",
]
