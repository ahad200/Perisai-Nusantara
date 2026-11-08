"""Aturan deteksi default + penanaman (PRD FR-102/203).

Aturan contoh dipetakan ke skenario simulator M3 agar demo M5 menghasilkan alert
dengan teknik ATT&CK yang benar.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.detection import DetectionRule, RuleStatus, RuleType, Severity

DEFAULT_RULES: list[dict] = [
    {
        "rule_code": "PNX-BF-001",
        "name": "Brute force — banyak login gagal",
        "type": RuleType.THRESHOLD.value,
        "severity": Severity.HIGH.value,
        "technique": "T1110", "technique_name": "Brute Force",
        "description": "≥10 login gagal dari sumber yang sama ke satu host dalam 15 menit.",
        "content": {
            "filter": {"source_type": "auth", "action": "login_failed"},
            "group_by": ["host", "src_ip"],
            "count": 10, "window_seconds": 900,
        },
    },
    {
        "rule_code": "PNX-RANSOM-001",
        "name": "Enkripsi massal berkas (indikasi ransomware)",
        "type": RuleType.THRESHOLD.value,
        "severity": Severity.CRITICAL.value,
        "technique": "T1486", "technique_name": "Data Encrypted for Impact",
        "description": "≥20 modifikasi berkas pada satu host dalam 15 menit.",
        "content": {
            "filter": {"source_type": "edr", "category": "file", "action": "file_modify"},
            "group_by": ["host"],
            "count": 20, "window_seconds": 900,
        },
    },
    {
        "rule_code": "PNX-SIGMA-PROC-001",
        "name": "Proses mencurigakan (masquerading)",
        "type": RuleType.SIGMA.value,
        "severity": Severity.HIGH.value,
        "technique": "T1036", "technique_name": "Masquerading",
        "description": "Proses dengan nama menyerupai proses sistem sah.",
        "content": {
            "selection": {
                "source_type": "edr", "action": "process_start",
                "raw.process": ["svch0st.exe", "scvhost.exe", "lsass.exe ", "mimikatz.exe"],
            },
        },
    },
    {
        "rule_code": "PNX-IOC-001",
        "name": "Pencocokan IoC terhadap event",
        "type": RuleType.IOC.value,
        "severity": Severity.MEDIUM.value,
        "technique": None, "technique_name": None,
        "description": "Event yang menyentuh IoC aktif (teknik diturunkan dari label IoC).",
        "content": {},
    },
]


def seed_rules(db: Session) -> list[str]:
    """Tanam aturan default (idempotent by rule_code). Return rule_code yang baru."""
    created: list[str] = []
    for r in DEFAULT_RULES:
        exists = db.execute(
            select(DetectionRule.id).where(DetectionRule.rule_code == r["rule_code"])
        ).scalar_one_or_none()
        if exists is not None:
            continue
        db.add(DetectionRule(status=RuleStatus.ENABLED.value, **r))
        created.append(r["rule_code"])
    db.commit()
    return created
