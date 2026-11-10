"""CLI collector berkas — verifikasi & ingest log asli dari JSONL/CSV.

Contoh:
    # Lihat dulu tanpa menulis (disarankan untuk sumber baru):
    python -m app.ingest.collectors file edr.jsonl --dry-run

    # Ingest sungguhan (seluruh berkas sebagai sumber `auth`):
    python -m app.ingest.collectors file winsec.csv --source auth --ts-field TimeCreated

Hanya membaca berkas lokal — tanpa egress (§A.5 no.5). Untuk sumber via API/syslog,
tulis subkelas `Collector` sendiri lalu panggil `run_collector(...)`.
"""
from __future__ import annotations

import argparse
import sys

from app.core.database import Base, SessionLocal, engine
from app.ingest.collectors.base import dry_run, run_collector
from app.ingest.collectors.file_tailer import FileCollector


def _ensure_tables() -> None:
    import app.models  # noqa: F401  registrasi model

    Base.metadata.create_all(bind=engine)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="app.ingest.collectors", description="Collector log asli → ingest PN-X"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("file", help="ingest berkas JSONL/CSV")
    p.add_argument("path", help="path berkas log")
    p.add_argument("--format", choices=["auto", "jsonl", "csv"], default="auto")
    p.add_argument("--source", default=None, help="paksa source_type untuk seluruh berkas")
    p.add_argument("--ts-field", default="ts", help="nama field timestamp (default: ts)")
    p.add_argument("--batch", type=int, default=500, help="ukuran batch commit/audit")
    p.add_argument("--actor", default="file-collector", help="actor_id untuk audit")
    p.add_argument("--dry-run", action="store_true", help="parse + normalisasi tanpa menulis DB")

    args = parser.parse_args(argv)
    if args.cmd != "file":  # pragma: no cover - argparse sudah menjamin
        parser.error("perintah tak dikenal")

    collector = FileCollector(
        args.path, fmt=args.format, source_override=args.source, ts_field=args.ts_field
    )

    if args.dry_run:
        report = dry_run(collector)
        print("DRY-RUN (tidak ada yang ditulis):")
        print(f"  per sumber   : {report['by_source'] or 'kosong'}")
        print(f"  per kategori : {report['by_category'] or 'kosong'}")
        print(f"  di-skip      : {report['skipped']}")
        if not report["by_source"]:
            print("  catatan: 0 record valid — cek --source / --ts-field / format berkas.")
            sys.exit(1)
        return

    _ensure_tables()
    result = run_collector(
        collector, SessionLocal, batch_size=args.batch, actor_id=args.actor
    )
    print(
        f"Ingest selesai: {result.ingested} event, {result.skipped} di-skip, "
        f"{result.batches} batch (= {result.batches} entri audit)."
    )


if __name__ == "__main__":  # pragma: no cover
    main()
