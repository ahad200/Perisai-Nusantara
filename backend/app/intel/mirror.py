"""Mirror enrichment lokal (PRD FR-202). Data **contoh**, diperbarui transfer satu arah.

Tidak ada panggilan jaringan: enrichment hanya hasil lookup ke tabel lokal
`enrichment_mirror`. Usia data (`mirror_updated_at`) ikut dikembalikan agar analis
tahu seberapa lama data mirror.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enrichment import EnrichmentKind, EnrichmentRecord
from app.models.ioc import utcnow_naive

# Data contoh mirror (bukan hasil query langsung). Disusun agar mencakup IoC yang
# dipakai skenario simulator M3 (C2 198.51.100.23, brute force 203.0.113.66, dll).
_NOW = None  # diisi saat seed agar umur data realistis


def _sample_rows() -> list[dict]:
    base_days = 3  # data mirror "berumur" beberapa hari
    updated = utcnow_naive() - timedelta(days=base_days)
    rows: list[dict] = []

    def add(key: str, kind: EnrichmentKind, source: str, data: dict):
        rows.append({"key": key, "kind": kind.value, "source": source,
                     "data": data, "mirror_updated_at": updated})

    # C2 beaconing (T1071)
    add("198.51.100.23", EnrichmentKind.GEOIP, "GeoIP mirror",
        {"country": "RU", "city": "Moscow", "asn": "AS56789", "org": "BulletHost LLC"})
    add("198.51.100.23", EnrichmentKind.WHOIS, "WHOIS mirror",
        {"netname": "BULLETHOST-NET", "registrar": "RIPE", "created": "2024-02-11"})
    add("198.51.100.23", EnrichmentKind.REPUTATION, "abuse.ch mirror",
        {"score": 92, "categories": ["c2", "malware"], "listed": True})
    add("sync-update.example.net", EnrichmentKind.WHOIS, "WHOIS mirror",
        {"registrar": "NiceRegistrar", "created": "2026-09-30", "age_days": 39})
    add("sync-update.example.net", EnrichmentKind.REPUTATION, "abuse.ch mirror",
        {"score": 88, "categories": ["c2"], "listed": True})

    # Brute force source (T1110)
    add("203.0.113.66", EnrichmentKind.GEOIP, "GeoIP mirror",
        {"country": "CN", "city": "Shanghai", "asn": "AS4134", "org": "Chinanet"})
    add("203.0.113.66", EnrichmentKind.REPUTATION, "abuse.ch mirror",
        {"score": 75, "categories": ["bruteforce", "scanner"], "listed": True})

    # IoC generik "bersih-ish"
    add("192.0.2.50", EnrichmentKind.GEOIP, "GeoIP mirror",
        {"country": "SG", "city": "Singapore", "asn": "AS9999", "org": "Example Cloud"})
    add("192.0.2.50", EnrichmentKind.REPUTATION, "abuse.ch mirror",
        {"score": 20, "categories": [], "listed": False})
    return rows


def seed_mirror(db: Session) -> int:
    """Isi tabel mirror dengan data contoh (idempotent by key+kind). Return baris baru."""
    created = 0
    for row in _sample_rows():
        exists = db.execute(
            select(EnrichmentRecord.id).where(
                EnrichmentRecord.key == row["key"],
                EnrichmentRecord.kind == row["kind"],
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue
        db.add(EnrichmentRecord(**row))
        created += 1
    db.commit()
    return created


def lookup_enrichment(db: Session, value: str) -> list[dict]:
    """Ambil semua enrichment mirror untuk sebuah nilai (IP/domain) + usia data."""
    rows = (
        db.execute(
            select(EnrichmentRecord)
            .where(EnrichmentRecord.key == value)
            .order_by(EnrichmentRecord.kind)
        )
        .scalars()
        .all()
    )
    now = utcnow_naive()
    out: list[dict] = []
    for r in rows:
        age_days = max(0, (now - r.mirror_updated_at).days)
        out.append({
            "kind": r.kind,
            "source": r.source,
            "data": r.data,
            "mirror_updated_at": r.mirror_updated_at,
            "mirror_age_days": age_days,
        })
    return out
