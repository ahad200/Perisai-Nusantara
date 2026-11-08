"""Uji integritas audit hash chain, termasuk deteksi tamper (FR-602)."""
from __future__ import annotations

from sqlalchemy import update

from app import audit
from app.core.rbac import Role
from app.models.audit import GENESIS_HASH, AuditEntry
from tests.conftest import bearer, login


def _seed_entries(db, n=5):
    for i in range(n):
        audit.record(
            db,
            action="test.event",
            actor_type="system",
            actor_id="pytest",
            object_type="thing",
            object_id=str(i),
            payload={"i": i},
        )


def test_chain_valid_after_appends(db_session):
    _seed_entries(db_session, 5)
    result = audit.verify_chain(db_session)
    assert result["ok"] is True
    assert result["count"] == 5
    assert result["broken_at"] is None


def test_first_entry_links_to_genesis(db_session):
    _seed_entries(db_session, 1)
    first = db_session.query(AuditEntry).order_by(AuditEntry.id.asc()).first()
    assert first.prev_hash == GENESIS_HASH


def test_each_entry_links_to_previous(db_session):
    _seed_entries(db_session, 4)
    entries = db_session.query(AuditEntry).order_by(AuditEntry.id.asc()).all()
    for prev, cur in zip(entries, entries[1:]):
        assert cur.prev_hash == prev.entry_hash


def test_tamper_field_detected(db_session):
    _seed_entries(db_session, 5)
    victim = db_session.query(AuditEntry).order_by(AuditEntry.id.asc()).all()[2]
    # Ubah 'action' langsung di DB tanpa memperbarui hash.
    db_session.execute(
        update(AuditEntry).where(AuditEntry.id == victim.id).values(action="DIPALSUKAN")
    )
    db_session.commit()

    result = audit.verify_chain(db_session)
    assert result["ok"] is False
    assert result["broken_at"] == victim.id


def test_tamper_with_recomputed_hash_breaks_next_link(db_session):
    """Bila penyerang mengubah field DAN menghitung ulang entry_hash satu entri,
    tautan prev_hash entri berikutnya menjadi tidak cocok."""
    _seed_entries(db_session, 5)
    entries = db_session.query(AuditEntry).order_by(AuditEntry.id.asc()).all()
    victim = entries[2]

    forged_hash = audit.compute_entry_hash(
        prev_hash=victim.prev_hash,
        ts=victim.ts,
        actor_type=victim.actor_type,
        actor_id=victim.actor_id,
        action="DIPALSUKAN",
        object_type=victim.object_type,
        object_id=victim.object_id,
        payload_hash_=victim.payload_hash,
    )
    db_session.execute(
        update(AuditEntry)
        .where(AuditEntry.id == victim.id)
        .values(action="DIPALSUKAN", entry_hash=forged_hash)
    )
    db_session.commit()

    result = audit.verify_chain(db_session)
    assert result["ok"] is False
    # Entri korban sendiri konsisten, tetapi entri berikutnya putus tautannya.
    assert result["broken_at"] == entries[3].id


def test_payload_hash_is_deterministic():
    h1 = audit.payload_hash({"b": 2, "a": 1})
    h2 = audit.payload_hash({"a": 1, "b": 2})
    assert h1 == h2  # urutan kunci tidak memengaruhi hash


def test_login_writes_audit_and_chain_stays_valid(client, make_user):
    make_user("cmd", Role.COMMANDER, "Password123!")
    make_user("aud", Role.AUDITOR, "Password123!")
    login(client, "cmd", "Password123!")  # tulis entri audit

    tok = login(client, "aud", "Password123!")["access_token"]
    entries = client.get("/audit", headers=bearer(tok))
    assert entries.status_code == 200
    assert any(e["action"] == "auth.login.success" for e in entries.json())

    v = client.get("/audit/verify", headers=bearer(tok))
    assert v.status_code == 200 and v.json()["ok"] is True
