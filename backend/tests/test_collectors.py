"""Uji kerangka collector (Fase 1 migrasi data asli, lihat docs/MIGRASI-DATA-ASLI.md).

Memakai SQLite in-memory via fixtures conftest — tanpa Docker.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.ingest.collectors import FileCollector, coerce_ts, dry_run, run_collector
from app.models.event import Event


# --- coerce_ts ------------------------------------------------------------

def test_coerce_ts_iso_with_z():
    dt = coerce_ts("2026-01-02T03:04:05Z")
    assert dt == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_coerce_ts_naive_gets_utc():
    dt = coerce_ts("2026-01-02T03:04:05")
    assert dt is not None and dt.tzinfo == timezone.utc


def test_coerce_ts_epoch_seconds_and_millis():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    secs = base.timestamp()
    assert coerce_ts(secs) == base
    assert coerce_ts(int(secs * 1000)) == base  # heuristik ms


@pytest.mark.parametrize("bad", [None, "", "bukan-tanggal", {}, []])
def test_coerce_ts_invalid_returns_none(bad):
    assert coerce_ts(bad) is None


# --- FileCollector + run_collector ---------------------------------------

def _write_jsonl(tmp_path, rows, name="log.jsonl"):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def test_run_collector_jsonl_ingests(tmp_path, SessionFactory, db_session):
    rows = [
        {"source_type": "auth", "ts": "2026-01-01T00:00:00Z", "user": "a", "host": "h1", "event": "login_failed"},
        {"source_type": "firewall", "ts": "2026-01-01T00:01:00Z", "host": "h1", "src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "dst_port": 443, "action": "allow", "bytes": 10},
    ]
    collector = FileCollector(_write_jsonl(tmp_path, rows))
    result = run_collector(collector, SessionFactory, actor_id="test")

    assert result.ingested == 2
    assert result.skipped == 0
    assert result.batches == 1
    total = db_session.execute(select(func.count()).select_from(Event)).scalar_one()
    assert total == 2


def test_run_collector_skips_bad_ts_and_malformed(tmp_path, SessionFactory, db_session):
    p = tmp_path / "mixed.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps({"source_type": "auth", "ts": "2026-01-01T00:00:00Z", "user": "a"}),
                json.dumps({"source_type": "auth", "ts": "tanggal-rusak", "user": "b"}),  # ts invalid
                json.dumps({"ts": "2026-01-01T00:00:00Z"}),  # tanpa source_type
                "{ bukan json }",  # baris rusak
                "",  # baris kosong diabaikan (bukan skip)
            ]
        ),
        encoding="utf-8",
    )
    result = run_collector(FileCollector(p), SessionFactory, actor_id="test")
    assert result.ingested == 1
    assert result.skipped == 3


def test_source_override_applies_to_all_rows(tmp_path, SessionFactory, db_session):
    rows = [{"ts": "2026-01-01T00:00:00Z", "user": "a", "host": "h1", "event": "login_success"}]
    collector = FileCollector(_write_jsonl(tmp_path, rows), source_override="auth")
    result = run_collector(collector, SessionFactory, actor_id="test")
    assert result.ingested == 1
    ev = db_session.execute(select(Event)).scalars().first()
    assert ev is not None and ev.source_type == "auth" and ev.category == "authentication"


def test_csv_with_custom_ts_field(tmp_path, SessionFactory, db_session):
    p = tmp_path / "winsec.csv"
    p.write_text(
        "source_type,TimeCreated,host,user,event\n"
        "auth,2026-01-01T00:00:00Z,h1,a,login_failed\n",
        encoding="utf-8",
    )
    collector = FileCollector(p, ts_field="TimeCreated")
    result = run_collector(collector, SessionFactory, actor_id="test")
    assert result.ingested == 1


def test_batching_produces_multiple_audit_batches(tmp_path, SessionFactory):
    rows = [
        {"source_type": "auth", "ts": "2026-01-01T00:00:00Z", "user": f"u{i}", "event": "login_success"}
        for i in range(5)
    ]
    collector = FileCollector(_write_jsonl(tmp_path, rows))
    result = run_collector(collector, SessionFactory, actor_id="test", batch_size=2)
    assert result.ingested == 5
    assert result.batches == 3  # 2 + 2 + 1


def test_dry_run_counts_without_writing(tmp_path, SessionFactory, db_session):
    rows = [
        {"source_type": "auth", "ts": "2026-01-01T00:00:00Z", "user": "a", "event": "login_failed"},
        {"source_type": "firewall", "ts": "2026-01-01T00:01:00Z", "host": "h1", "action": "deny"},
        {"source_type": "auth", "ts": "rusak"},  # di-skip
    ]
    report = dry_run(FileCollector(_write_jsonl(tmp_path, rows)))
    assert report["by_source"] == {"auth": 1, "firewall": 1}
    assert report["by_category"] == {"authentication": 1, "network": 1}
    assert report["skipped"] == 1
    # Tidak ada tulisan ke DB.
    total = db_session.execute(select(func.count()).select_from(Event)).scalar_one()
    assert total == 0
