"""Kerangka collector — jembatan dari sumber log ASLI ke pintu ingest tunggal.

Di prototipe, event diisi oleh `app/simulator/`. Untuk data asli, simulator diganti
collector: ia membaca log nyata (file/syslog/API EDR/firewall) dan menghasilkan
`RawRecord = (source_type, raw, ts)` — bentuk yang **sama persis** seperti yang
dipakai simulator — lalu diserahkan ke `app.ingest.ingest_events()`. Normalisasi,
penautan aset, dan audit per-batch ditangani di sana; collector tidak mengulangnya.

Modul ini sengaja TIDAK melakukan egress apa pun (PRD §A.5 no.5). Collector yang
menarik dari API eksternal harus berjalan sebagai proses TERPISAH di zona yang
diizinkan, lalu menyerahkan berkas/record ke sini — backend tetap air-gapped.

Alur pemakaian:

    collector = FileCollector("edr.jsonl")      # lihat file_tailer.py
    result = run_collector(collector, SessionLocal, actor_id="edr-collector")
    print(result)   # CollectResult(ingested=..., skipped=..., batches=...)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import sessionmaker

from app.ingest.normalize import normalize
from app.ingest.service import ingest_events

# Satu record mentah, identik dengan kontrak simulator → ingest_events.
RawRecord = tuple[str, dict[str, Any], datetime]


@dataclass(slots=True)
class CollectResult:
    """Ringkasan satu kali jalan collector."""

    ingested: int = 0  # event tersimpan ke DB
    skipped: int = 0  # record ditolak (ts/sumber tak valid)
    batches: int = 0  # jumlah batch yang di-commit (= jumlah AuditEntry ingest)

    def __str__(self) -> str:  # pragma: no cover - sekadar tampilan CLI
        return (
            f"CollectResult(ingested={self.ingested}, skipped={self.skipped}, "
            f"batches={self.batches})"
        )


def coerce_ts(value: Any) -> datetime | None:
    """Ubah nilai timestamp sumber apa adanya menjadi datetime UTC (aware).

    Menerima: epoch detik (int/float), epoch milidetik, atau string ISO-8601
    (dengan/ tanpa `Z`). Kembalikan `None` bila tak bisa diurai — pemanggil
    memperlakukannya sebagai record yang di-skip, bukan menebak waktu.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        # Heuristik ms vs s: > ~ tahun 2286 dalam detik ⇒ anggap milidetik.
        seconds = value / 1000.0 if value > 1e11 else float(value)
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # `datetime.fromisoformat` (Py3.11+) menerima offset & `Z`→gunakan ganti.
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            # Fallback: epoch dalam bentuk string.
            try:
                return coerce_ts(float(text))
            except ValueError:
                return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


class Collector(ABC):
    """Kontrak collector: hasilkan aliran `RawRecord`.

    Subkelas mengimplementasikan `read()`. Semua parsing format spesifik sumber
    tinggal di subkelas; base hanya tahu bentuk `(source_type, raw, ts)`.
    """

    #: Dipakai bila record tak membawa `source_type`-nya sendiri.
    source_default: str | None = None

    @abstractmethod
    def read(self) -> Iterator[RawRecord]:
        """Hasilkan record satu per satu. Record cacat sebaiknya di-skip di sini
        atau dibiarkan `run_collector` menolaknya (ts None → skip)."""
        raise NotImplementedError


def run_collector(
    collector: Collector,
    session_factory: sessionmaker,
    *,
    batch_size: int = 500,
    actor_id: str = "collector",
    scenario: str | None = None,
) -> CollectResult:
    """Alirkan record collector ke `ingest_events` dalam batch.

    Satu batch = satu commit = satu AuditEntry (§A.5 no.3), jadi ribuan event tak
    membanjiri rantai audit. Record dengan ts tak valid di-skip dan dihitung.
    """
    result = CollectResult()
    buffer: list[RawRecord] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        db = session_factory()
        try:
            result.ingested += ingest_events(
                db,
                buffer,
                scenario=scenario,
                action="event.ingest",
                actor_type="system",
                actor_id=actor_id,
            )
            result.batches += 1
        finally:
            db.close()
        buffer = []

    for source_type, raw, ts in collector.read():
        if ts is None or not source_type:
            result.skipped += 1
            continue
        buffer.append((source_type, raw, ts))
        if len(buffer) >= batch_size:
            flush()
    flush()
    return result


def dry_run(collector: Collector) -> dict[str, Any]:
    """Parse + normalisasi TANPA menulis ke DB (sejajar dengan dry-run SOAR, FR-306).

    Dipakai untuk memverifikasi collector/normalizer sumber baru sebelum data benar-
    benar masuk. Mengembalikan hitungan per source_type & per kategori ternormalisasi.
    """
    by_source: dict[str, int] = {}
    by_category: dict[str, int] = {}
    skipped = 0
    for source_type, raw, ts in collector.read():
        if ts is None or not source_type:
            skipped += 1
            continue
        n = normalize(source_type, raw, ts)
        by_source[n.source_type] = by_source.get(n.source_type, 0) + 1
        by_category[n.category] = by_category.get(n.category, 0) + 1
    return {"by_source": by_source, "by_category": by_category, "skipped": skipped}
