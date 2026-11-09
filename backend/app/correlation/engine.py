"""Mesin korelasi alert -> insiden (PRD M7, FR-204).

Strategi (prototipe, deterministik, tanpa dependensi):
- Pertimbangkan hanya alert **aktif** (bukan false-positive yang sudah ditutup).
- Kelompokkan berdasarkan **entitas utama**: host (fallback `asset:<id>`, lalu
  "unassigned"). Semua alert pada entitas yang sama menyusun satu insiden — ini
  menangkap narasi rantai serangan pada satu aset (mis. T1110 -> T1071 -> T1486).
- `correlation_key = "host:<host>"` membuat korelasi **idempotent**: menjalankan
  ulang akan memperbarui insiden yang sama, bukan membuat duplikat.

Agregat (severity tertinggi, teknik ATT&CK unik, rentang waktu, jumlah alert)
didenormalisasi ke baris insiden untuk tampilan papan & cakupan ATT&CK.

Status siklus hidup yang sudah diubah analis **tidak** ditimpa oleh korelasi;
korelasi hanya menetapkan status awal `open` saat insiden pertama dibuat.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models.alert import Alert, AlertStatus
from app.models.asset import Asset
from app.models.detection import SEVERITY_RANK, Severity
from app.models.incident import (
    Incident,
    IncidentNote,
    IncidentStatus,
    NoteKind,
)

# Alert dengan status ini tidak dikorelasikan (sudah ditutup sebagai false positive).
_EXCLUDED_ALERT_STATUSES = frozenset({AlertStatus.CLOSED_FP.value})


def _entity_key(alert: Alert) -> tuple[str, str | None]:
    """(correlation_key, host) untuk sebuah alert."""
    if alert.host:
        return f"host:{alert.host}", alert.host
    if alert.asset_id is not None:
        return f"asset:{alert.asset_id}", None
    return "unassigned", None


def _max_severity(severities: list[str]) -> str:
    return max(
        severities,
        key=lambda s: SEVERITY_RANK.get(s, 0),
        default=Severity.INFO.value,
    )


def _collect_techniques(alerts: list[Alert]) -> list[dict]:
    """Daftar teknik ATT&CK unik (terurut) dari alert anggota — cakupan per insiden."""
    seen: dict[str, str | None] = {}
    for a in alerts:
        if a.technique and a.technique not in seen:
            seen[a.technique] = a.technique_name
    return [
        {"technique": t, "name": seen[t]}
        for t in sorted(seen)
    ]


def _summary(host: str | None, alerts: list[Alert], techniques: list[dict]) -> tuple[str, str]:
    where = host or "aset tak dikenal"
    tech_str = ", ".join(t["technique"] for t in techniques) or "tanpa teknik terpetakan"
    title = f"Insiden pada {where} — {len(alerts)} alert"
    summary = (
        f"{len(alerts)} alert terkorelasi pada {where}. "
        f"Teknik ATT&CK: {tech_str}."
    )
    return title, summary


def correlate(
    db: Session, *, actor_id: str | None = "correlation", actor_type: str = "system",
    record_audit: bool = True,
) -> dict[str, Any]:
    """Kelompokkan alert aktif menjadi insiden. Idempotent. Kembalikan ringkasan."""
    alerts = db.execute(
        select(Alert).where(Alert.status.not_in(_EXCLUDED_ALERT_STATUSES))
    ).scalars().all()

    groups: dict[str, tuple[str | None, list[Alert]]] = {}
    for a in alerts:
        key, host = _entity_key(a)
        if key not in groups:
            groups[key] = (host, [])
        groups[key][1].append(a)

    asset_map = {h: i for h, i in db.execute(select(Asset.hostname, Asset.id)).all()}

    created = updated = 0
    for key, (host, members) in groups.items():
        members.sort(key=lambda a: (a.first_event_ts or a.created_at))
        severity = _max_severity([a.severity for a in members])
        techniques = _collect_techniques(members)
        title, summary = _summary(host, members, techniques)
        firsts = [a.first_event_ts for a in members if a.first_event_ts]
        lasts = [a.last_event_ts for a in members if a.last_event_ts]
        first_ts = min(firsts) if firsts else None
        last_ts = max(lasts) if lasts else None

        inc = db.execute(
            select(Incident).where(Incident.correlation_key == key)
        ).scalar_one_or_none()

        if inc is None:
            inc = Incident(
                correlation_key=key, incident_code="",  # diisi setelah flush (butuh id)
                title=title, summary=summary, severity=severity,
                status=IncidentStatus.OPEN.value,
                asset_id=asset_map.get(host) if host else None, host=host,
                techniques=techniques, alert_count=len(members),
                first_event_ts=first_ts, last_event_ts=last_ts,
            )
            db.add(inc)
            db.flush()  # dapatkan id untuk incident_code
            inc.incident_code = f"INC-{inc.id:05d}"
            db.add(IncidentNote(
                incident_id=inc.id, author=actor_id or "correlation", kind=NoteKind.SYSTEM.value,
                body=f"Insiden dibuat oleh korelasi dari {len(members)} alert pada {host or key}.",
            ))
            created += 1
        else:
            prev_count = inc.alert_count
            inc.title, inc.summary = title, summary
            inc.severity = severity
            inc.techniques = techniques
            inc.alert_count = len(members)
            inc.first_event_ts, inc.last_event_ts = first_ts, last_ts
            if host and inc.asset_id is None:
                inc.asset_id = asset_map.get(host)
            if len(members) != prev_count:
                db.add(IncidentNote(
                    incident_id=inc.id, author=actor_id or "correlation", kind=NoteKind.SYSTEM.value,
                    body=f"Korelasi diperbarui: {prev_count} -> {len(members)} alert.",
                ))
            updated += 1

        # Tetapkan keanggotaan (idempotent).
        for a in members:
            a.incident_id = inc.id

    db.commit()

    result = {
        "incidents": len(groups),
        "created": created,
        "updated": updated,
        "alerts_correlated": len(alerts),
    }
    if record_audit:
        audit.record(
            db, action="incident.correlate", actor_type=actor_type, actor_id=actor_id,
            object_type="incident", payload=result,
        )
    return result
