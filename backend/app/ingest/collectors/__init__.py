"""Collector data asli (pengganti simulator untuk ingest produksi).

Lihat `docs/MIGRASI-DATA-ASLI.md` Fase 1. Kerangka di `base.py`; contoh berjalan
untuk berkas JSONL/CSV di `file_tailer.py`.
"""
from app.ingest.collectors.base import (
    CollectResult,
    Collector,
    RawRecord,
    coerce_ts,
    dry_run,
    run_collector,
)
from app.ingest.collectors.file_tailer import FileCollector

__all__ = [
    "Collector",
    "CollectResult",
    "RawRecord",
    "FileCollector",
    "coerce_ts",
    "dry_run",
    "run_collector",
]
