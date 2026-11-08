"""Ingest & normalisasi event (PRD §5 langkah 1, FR-101).

`normalize.normalize()` memetakan muatan sumber (EDR/firewall/auth/proxy — data
simulasi) ke skema umum ala ECS/OCSF. `service.ingest_events()` menyimpannya ke
tabel `events`, menautkan ke `Asset` berdasarkan hostname, dan menulis satu
AuditEntry per batch (PRD §A.5 no.3).
"""
from app.ingest.normalize import NormalizedEvent, normalize
from app.ingest.service import ingest_events

__all__ = ["normalize", "NormalizedEvent", "ingest_events"]
