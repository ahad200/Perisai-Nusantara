"""Collector contoh: baca berkas log JSONL atau CSV → RawRecord.

Ini skeleton yang SUDAH berjalan untuk sumber paling umum (ekspor log sebagai
JSON-lines atau CSV). Dua titik yang biasanya perlu Anda sesuaikan per sumber:

1. `source_type` — dari kolom `source_type` di berkas, atau paksa lewat
   `source_override` (mis. seluruh berkas adalah log `auth`).
2. Nama field timestamp — default `ts`; ganti lewat `ts_field`.

Format `raw` yang dihasilkan diteruskan apa adanya ke `normalize()`. Pastikan ada
fungsi normalizer untuk `source_type` tsb di `app/ingest/normalize.py` (sumber tak
dikenal tetap masuk sebagai kategori `other`, tidak hilang).

Catatan air-gap: collector ini hanya membaca berkas lokal — tanpa jaringan. Untuk
sumber via API, tulis subkelas `Collector` terpisah dan jalankan di zona yang
diizinkan; backend tetap tidak melakukan egress (§A.5 no.5).
"""
from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from pathlib import Path

from app.ingest.collectors.base import Collector, RawRecord, coerce_ts


class FileCollector(Collector):
    def __init__(
        self,
        path: str | Path,
        *,
        fmt: str = "auto",  # auto | jsonl | csv
        source_override: str | None = None,
        ts_field: str = "ts",
    ) -> None:
        self.path = Path(path)
        self.fmt = fmt
        self.source_override = source_override
        self.source_default = source_override
        self.ts_field = ts_field

    def _resolved_fmt(self) -> str:
        if self.fmt != "auto":
            return self.fmt
        suffix = self.path.suffix.lower()
        if suffix == ".csv":
            return "csv"
        return "jsonl"  # .jsonl / .json / .log → satu objek JSON per baris

    def _to_record(self, raw: dict) -> RawRecord | tuple[None, dict, None]:
        source_type = self.source_override or str(raw.get("source_type") or "").strip()
        ts = coerce_ts(raw.get(self.ts_field))
        # (None, …) ditolak oleh run_collector/dry_run dan dihitung sebagai skipped.
        if not source_type or ts is None:
            return (None, raw, None)
        return (source_type, raw, ts)

    def read(self) -> Iterator[RawRecord]:
        fmt = self._resolved_fmt()
        with self.path.open("r", encoding="utf-8", newline="") as fh:
            if fmt == "csv":
                for raw in csv.DictReader(fh):
                    yield self._to_record(dict(raw))
            else:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        yield (None, {"_raw_line": line}, None)  # skip + hitung
                        continue
                    if isinstance(raw, dict):
                        yield self._to_record(raw)
                    else:
                        yield (None, {"_raw_line": line}, None)
