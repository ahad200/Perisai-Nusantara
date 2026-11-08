"""Penyimpanan event ternormalisasi + penautan ke inventaris aset.

Satu batch ingest = satu AuditEntry (PRD §A.5 no.3), bukan satu per event, agar
rantai audit tidak dibanjiri ribuan entri dari simulator.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.ingest.normalize import normalize
from app.models.asset import Asset
from app.models.event import Event

# Satu record mentah: (source_type, raw, ts).
RawRecord = tuple[str, dict[str, Any], datetime]


def _host_to_asset_id(db: Session) -> dict[str, int]:
    rows = db.execute(select(Asset.hostname, Asset.id)).all()
    return {hostname: asset_id for hostname, asset_id in rows}


def ingest_events(
    db: Session,
    records: Iterable[RawRecord],
    *,
    scenario: str | None = None,
    action: str = "event.ingest",
    actor_type: str = "system",
    actor_id: str | None = "simulator",
    record_audit: bool = True,
) -> int:
    """Normalisasi + simpan batch event. Mengembalikan jumlah event tersimpan.

    `asset_id` ditautkan bila `host` cocok dengan `Asset.hostname`; host di luar
    inventaris tetap disimpan (asset_id=None) agar tidak ada kehilangan visibilitas.
    """
    host_map = _host_to_asset_id(db)
    objects: list[Event] = []
    by_source: dict[str, int] = {}

    for source_type, raw, ts in records:
        n = normalize(source_type, raw, ts)
        by_source[n.source_type] = by_source.get(n.source_type, 0) + 1
        objects.append(
            Event(
                ts=n.ts,
                source_type=n.source_type,
                host=n.host,
                asset_id=host_map.get(n.host) if n.host else None,
                category=n.category,
                action=n.action,
                outcome=n.outcome,
                user=n.user,
                src_ip=n.src_ip,
                dst_ip=n.dst_ip,
                dst_port=n.dst_port,
                bytes_out=n.bytes_out,
                message=n.message[:512],
                scenario=scenario,
                raw=n.raw,
            )
        )

    if not objects:
        return 0

    db.add_all(objects)
    db.commit()

    if record_audit:
        audit.record(
            db,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            object_type="event_batch",
            object_id=scenario,
            payload={"scenario": scenario, "count": len(objects), "by_source": by_source},
        )
    return len(objects)
