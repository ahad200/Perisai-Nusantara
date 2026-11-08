"""Mesin deteksi (PRD M5, FR-102/203).

Tiga jalur deteksi di prototipe:
- `sigma`     : kecocokan field (subset Sigma) atas event ternormalisasi.
- `threshold` : agregasi (mis. brute force = N login gagal dalam jendela waktu).
- `ioc`       : pencocokan IoC aktif (M4) terhadap event; teknik ATT&CK diturunkan
                dari label IoC.

Setiap alert membawa **teknik MITRE ATT&CK** (FR-203) dan dirujuk ke event
penyebab. Deteksi **idempotent** lewat `dedup_key`.
"""
from app.detection.anomaly import detect_anomalies
from app.detection.engine import run_detection
from app.detection.rules import DEFAULT_RULES, seed_rules

__all__ = ["run_detection", "seed_rules", "DEFAULT_RULES", "detect_anomalies"]
