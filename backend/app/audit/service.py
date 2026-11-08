"""Layanan audit hash chain (PRD §12, FR-602).

Properti yang dijamin:
- **Append-only**: hanya menambah entri; tidak ada update/hapus.
- **Tamper-evident**: setiap entri merantai `prev_hash` -> `entry_hash`.
  Mengubah field apa pun pada satu entri membuat `verify_chain` menandai posisinya.

Catatan konkurensi (prototipe): penambahan diserialkan dengan lock proses tunggal.
Produksi berskala banyak-proses sebaiknya memakai advisory lock DB / writer tunggal.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import GENESIS_HASH, AuditEntry

_append_lock = threading.Lock()


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def payload_hash(payload: dict[str, Any] | None) -> str:
    """Hash kanonik dari payload (JSON sorted-keys). Payload mentah tidak disimpan."""
    canonical = json.dumps(
        payload or {},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return _sha256_hex(canonical)


def _iso(dt: datetime) -> str:
    """Representasi waktu kanonik: UTC naif, mikrodetik — stabil lintas backend DB."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(timespec="microseconds")


def compute_entry_hash(
    *,
    prev_hash: str,
    ts: datetime,
    actor_type: str,
    actor_id: str | None,
    action: str,
    object_type: str | None,
    object_id: str | None,
    payload_hash_: str,
) -> str:
    """SHA-256 atas seluruh field terikat, dipisah '|' (NUL-safe karena di-escape JSON)."""
    parts = [
        prev_hash,
        _iso(ts),
        actor_type,
        actor_id or "",
        action,
        object_type or "",
        object_id or "",
        payload_hash_,
    ]
    return _sha256_hex("|".join(parts))


def _last_entry(db: Session) -> AuditEntry | None:
    return db.execute(
        select(AuditEntry).order_by(AuditEntry.id.desc()).limit(1)
    ).scalar_one_or_none()


def record(
    db: Session,
    *,
    action: str,
    payload: dict[str, Any] | None = None,
    actor_type: str = "system",
    actor_id: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
) -> AuditEntry:
    """Menambahkan satu entri audit dan meng-commit-nya. Mengembalikan entri baru.

    Commit dilakukan di sini agar rantai audit tetap utuh dan tak terpengaruh
    rollback pemanggil.
    """
    with _append_lock:
        prev = _last_entry(db)
        prev_hash = prev.entry_hash if prev else GENESIS_HASH

        # Simpan ts sebagai UTC naif agar konsisten dengan _iso saat verifikasi.
        ts = datetime.now(timezone.utc).replace(tzinfo=None)
        p_hash = payload_hash(payload)
        entry_hash = compute_entry_hash(
            prev_hash=prev_hash,
            ts=ts,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            payload_hash_=p_hash,
        )
        entry = AuditEntry(
            ts=ts,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            payload_hash=p_hash,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry


def verify_chain(db: Session) -> dict[str, Any]:
    """Memverifikasi integritas seluruh rantai.

    Returns dict:
      ok: bool                 — True bila rantai utuh.
      count: int               — jumlah entri diperiksa.
      broken_at: int | None    — id entri pertama yang gagal (None bila utuh).
      reason: str | None       — alasan kegagalan.
    """
    entries = db.execute(select(AuditEntry).order_by(AuditEntry.id.asc())).scalars().all()
    expected_prev = GENESIS_HASH

    for e in entries:
        # 1) Link rantai: prev_hash entri harus sama dengan hash entri sebelumnya.
        if e.prev_hash != expected_prev:
            return {
                "ok": False,
                "count": len(entries),
                "broken_at": e.id,
                "reason": "prev_hash tidak cocok dengan hash entri sebelumnya",
            }
        # 2) Integritas entri: hitung ulang hash dari field tersimpan.
        recomputed = compute_entry_hash(
            prev_hash=e.prev_hash,
            ts=e.ts,
            actor_type=e.actor_type,
            actor_id=e.actor_id,
            action=e.action,
            object_type=e.object_type,
            object_id=e.object_id,
            payload_hash_=e.payload_hash,
        )
        if recomputed != e.entry_hash:
            return {
                "ok": False,
                "count": len(entries),
                "broken_at": e.id,
                "reason": "hash entri tidak cocok (field telah diubah)",
            }
        expected_prev = e.entry_hash

    return {"ok": True, "count": len(entries), "broken_at": None, "reason": None}
