"""Library playbook SOAR (PRD FR-301) + seeding idempotent.

Playbook memetakan **teknik ATT&CK pemicu** ke urutan langkah respons. Tiap
langkah menyebut `action` (lihat `adapters.ACTION_CATALOG`), `params`, dan penanda
`disruptive`/`pre_approved` yang memengaruhi keputusan Matriks Otonomi (§7).

`pre_approved: true` = aksi yang sudah disetujui CAB untuk skenario tsb (mis.
isolasi endpoint saat ransomware) sehingga bisa auto pada sel Critical × K2 (§7).
Playbook punya **versi & pemilik** (FR-301).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.soar import Playbook, PlaybookStatus

# code, name, trigger_technique, owner, description, steps
DEFAULT_PLAYBOOKS: list[dict] = [
    {
        "code": "PNX-PB-RANSOM",
        "name": "Containment Ransomware (T1486)",
        "trigger_technique": "T1486",
        "owner": "intel",
        "description": "Isolasi host terenkripsi, kumpulkan forensik, blokir indikator.",
        "steps": [
            {"action": "isolate_host", "params": {}, "disruptive": True, "pre_approved": True},
            {"action": "collect_forensics", "params": {"scope": "disk+memory"}, "disruptive": False, "pre_approved": False},
            {"action": "block_ip", "params": {}, "disruptive": False, "pre_approved": False},
        ],
    },
    {
        "code": "PNX-PB-BRUTEFORCE",
        "name": "Respons Brute Force (T1110)",
        "trigger_technique": "T1110",
        "owner": "operator",
        "description": "Blokir sumber, cabut sesi akun target, naikkan logging.",
        "steps": [
            {"action": "block_ip", "params": {}, "disruptive": False, "pre_approved": False},
            {"action": "revoke_token", "params": {}, "disruptive": True, "pre_approved": False},
            {"action": "raise_logging", "params": {"level": "debug"}, "disruptive": False, "pre_approved": False},
        ],
    },
    {
        "code": "PNX-PB-BEACON",
        "name": "Respons Beaconing C2 (T1071)",
        "trigger_technique": "T1071",
        "owner": "operator",
        "description": "Blokir C2 di perimeter, tambahkan ke watchlist, kumpulkan artefak.",
        "steps": [
            {"action": "block_ip", "params": {}, "disruptive": False, "pre_approved": False},
            {"action": "add_watchlist", "params": {}, "disruptive": False, "pre_approved": False},
            {"action": "collect_forensics", "params": {"scope": "network"}, "disruptive": False, "pre_approved": False},
        ],
    },
    {
        "code": "PNX-PB-SUSPROC",
        "name": "Respons Proses Mencurigakan (T1036)",
        "trigger_technique": "T1036",
        "owner": "operator",
        "description": "Isolasi host, kumpulkan forensik.",
        "steps": [
            {"action": "isolate_host", "params": {}, "disruptive": True, "pre_approved": False},
            {"action": "collect_forensics", "params": {"scope": "process"}, "disruptive": False, "pre_approved": False},
        ],
    },
]


def seed_playbooks(db: Session) -> int:
    """Tanam playbook default (idempotent). Kembalikan jumlah yang baru dibuat."""
    created = 0
    for pb in DEFAULT_PLAYBOOKS:
        exists = db.execute(
            select(Playbook.id).where(Playbook.code == pb["code"])
        ).scalar_one_or_none()
        if exists is not None:
            continue
        db.add(Playbook(
            code=pb["code"], name=pb["name"], trigger_technique=pb["trigger_technique"],
            owner=pb["owner"], description=pb["description"], steps=pb["steps"],
            status=PlaybookStatus.ACTIVE.value, version=1,
        ))
        created += 1
    db.commit()
    return created


def playbook_for_technique(db: Session, technique: str | None) -> Playbook | None:
    if not technique:
        return None
    return db.execute(
        select(Playbook).where(
            Playbook.trigger_technique == technique,
            Playbook.status == PlaybookStatus.ACTIVE.value,
        )
    ).scalars().first()
