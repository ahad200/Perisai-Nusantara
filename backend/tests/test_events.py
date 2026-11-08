"""Test penjelajah event: filter, pagination, detail (M3)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.rbac import Role
from app.ingest import ingest_events
from app.simulator.fleet import seed_assets

from tests.conftest import bearer, login

T0 = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)


def _seed_events(db):
    seed_assets(db, record_audit=False)
    recs = [
        ("auth", {"host": "cmd-core-01", "user": "admin", "src_ip": "10.10.1.10", "event": "login_success"}, T0),
        ("auth", {"host": "app-logistik-01", "user": "x", "src_ip": "203.0.113.1", "event": "login_failed"}, T0 + timedelta(minutes=1)),
        ("firewall", {"host": "ws-staff-01", "src_ip": "10.10.3.31", "dst_ip": "10.10.1.10", "dst_port": 443, "action": "allow", "bytes": 800}, T0 + timedelta(minutes=2)),
    ]
    ingest_events(db, recs, scenario="unittest", record_audit=False)


def _token(client, make_user, username, role):
    make_user(username, role)
    return login(client, username, "Password123!")["access_token"]


def test_list_events_and_total(client, make_user, db_session):
    _seed_events(db_session)
    tok = _token(client, make_user, "a1", Role.ANALYST_T1)
    r = client.get("/events", headers=bearer(tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    # Urutan terbaru dulu (ts desc).
    assert body["items"][0]["source_type"] == "firewall"


def test_filter_by_source_type(client, make_user, db_session):
    _seed_events(db_session)
    tok = _token(client, make_user, "a1", Role.ANALYST_T1)
    r = client.get("/events?source_type=auth", headers=bearer(tok))
    body = r.json()
    assert body["total"] == 2
    assert all(i["source_type"] == "auth" for i in body["items"])


def test_filter_by_scenario_and_search(client, make_user, db_session):
    _seed_events(db_session)
    tok = _token(client, make_user, "a1", Role.ANALYST_T1)
    assert client.get("/events?scenario=unittest", headers=bearer(tok)).json()["total"] == 3
    r = client.get("/events?q=203.0.113.1", headers=bearer(tok))
    assert r.json()["total"] == 1


def test_event_has_asset_criticality(client, make_user, db_session):
    _seed_events(db_session)
    tok = _token(client, make_user, "a1", Role.ANALYST_T1)
    r = client.get("/events?host=cmd-core-01", headers=bearer(tok))
    item = r.json()["items"][0]
    assert item["asset_criticality"] == "K1"


def test_pagination(client, make_user, db_session):
    _seed_events(db_session)
    tok = _token(client, make_user, "a1", Role.ANALYST_T1)
    r = client.get("/events?limit=2&offset=0", headers=bearer(tok))
    body = r.json()
    assert body["total"] == 3 and len(body["items"]) == 2


def test_event_detail_includes_raw(client, make_user, db_session):
    _seed_events(db_session)
    tok = _token(client, make_user, "a1", Role.ANALYST_T1)
    first_id = client.get("/events", headers=bearer(tok)).json()["items"][0]["id"]
    r = client.get(f"/events/{first_id}", headers=bearer(tok))
    assert r.status_code == 200
    assert "raw" in r.json() and isinstance(r.json()["raw"], dict)


def test_event_requires_auth(client):
    assert client.get("/events").status_code in (401, 403)
