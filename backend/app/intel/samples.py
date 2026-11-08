"""Bundle STIX 2.1 contoh + penanaman intel (data simulasi) untuk demo M4.

Indikator sengaja mencakup IoC dari skenario simulator M3 (C2 198.51.100.23 &
domainnya, sumber brute force 203.0.113.66, hash ransomware) agar M5 bisa
mencocokkan event dengan IoC. Satu indikator dibuat **kedaluwarsa** untuk
mendemokan siklus hidup (FR-205).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.intel.mirror import seed_mirror
from app.intel.stix_import import import_bundle
from app.models.ioc import Tlp

# Marking-definition TLP standar (dipakai lewat object_marking_refs).
_TLP_AMBER = "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"
_TLP_GREEN = "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da"
_TLP_RED = "marking-definition--5e57c739-391a-4eb3-b6be-7d15ca92d5ed"

SAMPLE_BUNDLE: dict[str, Any] = {
    "type": "bundle",
    "id": "bundle--pnx-sample-0001",
    "objects": [
        {"type": "marking-definition", "id": _TLP_AMBER, "definition_type": "tlp",
         "name": "TLP:AMBER", "definition": {"tlp": "amber"}},
        {"type": "marking-definition", "id": _TLP_GREEN, "definition_type": "tlp",
         "name": "TLP:GREEN", "definition": {"tlp": "green"}},
        {"type": "marking-definition", "id": _TLP_RED, "definition_type": "tlp",
         "name": "TLP:RED", "definition": {"tlp": "red"}},
        {
            "type": "indicator", "spec_version": "2.1",
            "id": "indicator--c2-ip-0001", "created": "2026-10-20T00:00:00Z",
            "valid_from": "2026-10-20T00:00:00Z", "valid_until": "2027-06-01T00:00:00Z",
            "name": "C2 server (beaconing)", "confidence": 90,
            "labels": ["malicious-activity", "c2"],
            "pattern_type": "stix", "pattern": "[ipv4-addr:value = '198.51.100.23']",
            "object_marking_refs": [_TLP_AMBER],
        },
        {
            "type": "indicator", "spec_version": "2.1",
            "id": "indicator--c2-domain-0001", "created": "2026-10-20T00:00:00Z",
            "valid_from": "2026-10-20T00:00:00Z", "valid_until": "2027-06-01T00:00:00Z",
            "name": "C2 domain (beaconing)", "confidence": 85,
            "labels": ["malicious-activity", "c2"],
            "pattern_type": "stix", "pattern": "[domain-name:value = 'sync-update.example.net']",
            "object_marking_refs": [_TLP_AMBER],
        },
        {
            "type": "indicator", "spec_version": "2.1",
            "id": "indicator--bruteforce-ip-0001", "created": "2026-10-25T00:00:00Z",
            "valid_from": "2026-10-25T00:00:00Z", "valid_until": "2027-03-01T00:00:00Z",
            "name": "Brute force source", "confidence": 70,
            "labels": ["scanner", "bruteforce"],
            "pattern_type": "stix", "pattern": "[ipv4-addr:value = '203.0.113.66']",
            "object_marking_refs": [_TLP_AMBER],
        },
        {
            "type": "indicator", "spec_version": "2.1",
            "id": "indicator--ransomware-hash-0001", "created": "2026-11-01T00:00:00Z",
            "valid_from": "2026-11-01T00:00:00Z",
            "name": "Ransomware payload (svch0st.exe)", "confidence": 95,
            "labels": ["malicious-activity", "ransomware"],
            "pattern_type": "stix",
            "pattern": "[file:hashes.'SHA-256' = 'a1b2c3d4e5f6071829304152637485960718293041526374859607182930a1b2']",
            "object_marking_refs": [_TLP_RED],
        },
        {
            "type": "indicator", "spec_version": "2.1",
            "id": "indicator--stale-ip-0001", "created": "2026-08-01T00:00:00Z",
            "valid_from": "2026-08-01T00:00:00Z", "valid_until": "2026-10-01T00:00:00Z",
            "name": "Indikator lama (sudah kedaluwarsa)", "confidence": 30,
            "labels": ["anomalous-activity"],
            "pattern_type": "stix", "pattern": "[ipv4-addr:value = '192.0.2.50']",
            "object_marking_refs": [_TLP_GREEN],
        },
    ],
}


def seed_intel(db: Session, *, record_audit: bool = True) -> dict[str, Any]:
    """Tanam mirror enrichment + impor bundle STIX contoh. Idempotent."""
    mirror = seed_mirror(db)
    result = import_bundle(
        db, SAMPLE_BUNDLE, default_source="Bundle contoh (MISP)", record_audit=record_audit
    )
    return {"mirror_rows": mirror, **result}
