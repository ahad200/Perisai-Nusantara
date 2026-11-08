"""Test normalisasi & ingest event (M3)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.ingest import ingest_events, normalize
from app.models.event import Event
from app.simulator.fleet import seed_assets

TS = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)


def test_normalize_auth_failure():
    n = normalize("auth", {"host": "h1", "user": "ucok", "src_ip": "1.2.3.4", "event": "login_failed"}, TS)
    assert n.category == "authentication"
    assert n.action == "login_failed"
    assert n.outcome == "failure"
    assert n.user == "ucok" and n.src_ip == "1.2.3.4"


def test_normalize_firewall_deny():
    n = normalize("firewall", {"host": "h1", "src_ip": "1.1.1.1", "dst_ip": "2.2.2.2",
                               "dst_port": 445, "action": "deny", "bytes": 1200}, TS)
    assert n.category == "network"
    assert n.action == "flow_deny" and n.outcome == "failure"
    assert n.dst_port == 445 and n.bytes_out == 1200


def test_normalize_edr_encrypt_is_file_category():
    n = normalize("edr", {"host": "h1", "process": "x.exe", "action": "file_encrypt", "file_count": 120}, TS)
    assert n.category == "file"
    assert n.action == "file_modify"


def test_normalize_unknown_source_is_other():
    n = normalize("weirdsrc", {"host": "h1", "action": "blah"}, TS)
    assert n.category == "other"
    assert n.source_type == "weirdsrc"


def test_ingest_links_asset_by_hostname(db_session):
    seed_assets(db_session, record_audit=False)
    count = ingest_events(
        db_session,
        [
            ("auth", {"host": "cmd-core-01", "user": "admin", "src_ip": "10.10.1.10", "event": "login_success"}, TS),
            ("auth", {"host": "unknown-host-99", "user": "x", "src_ip": "9.9.9.9", "event": "login_failed"}, TS),
        ],
        scenario="test",
        record_audit=False,
    )
    assert count == 2
    linked = db_session.query(Event).filter(Event.host == "cmd-core-01").one()
    assert linked.asset_id is not None
    orphan = db_session.query(Event).filter(Event.host == "unknown-host-99").one()
    assert orphan.asset_id is None  # host di luar inventaris tetap tersimpan


def test_ingest_empty_is_noop(db_session):
    assert ingest_events(db_session, [], record_audit=False) == 0
