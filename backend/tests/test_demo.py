"""Test perintah isi data demo (`python -m app.demo`)."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app import demo
from app.models.event import Event
from app.models.incident import Incident
from app.models.soar import Approval, PlaybookRun
from app.models.user import User


def test_populate_fills_dashboard_and_is_rerunnable(SessionFactory, engine):
    s1 = demo.populate(session_factory=SessionFactory, bind=engine)
    db = SessionFactory()
    try:
        assert db.execute(select(func.count(User.id))).scalar_one() == 4
        events = db.execute(select(func.count(Event.id))).scalar_one()
        incidents = db.execute(select(func.count(Incident.id))).scalar_one()
        runs = db.execute(select(func.count(PlaybookRun.id))).scalar_one()
        assert events > 1000 and incidents >= 1 and runs >= 1
        assert s1["playbook_runs"] == runs
    finally:
        db.close()

    # Dijalankan ulang: tak menggandakan event/insiden/run.
    s2 = demo.populate(session_factory=SessionFactory, bind=engine)
    db = SessionFactory()
    try:
        assert db.execute(select(func.count(Event.id))).scalar_one() == events
        assert db.execute(select(func.count(Incident.id))).scalar_one() == incidents
        assert db.execute(select(func.count(PlaybookRun.id))).scalar_one() == runs
        assert s2["users_created"] == [] and s2["playbook_runs"] == 0
    finally:
        db.close()


def test_playbooks_go_through_autonomy_matrix(SessionFactory, engine):
    """Demo memakai app.soar (bukan adapter langsung): ada keputusan approval/auto tercatat."""
    demo.populate(session_factory=SessionFactory, bind=engine)
    db = SessionFactory()
    try:
        statuses = set(db.execute(select(PlaybookRun.status)).scalars().all())
        assert statuses & {"completed", "awaiting_approval"}
        if "awaiting_approval" in statuses:
            assert db.execute(select(func.count(Approval.id))).scalar_one() >= 1
    finally:
        db.close()


def test_reset_refused_in_prod(monkeypatch):
    class _S:
        is_prod = True
    monkeypatch.setattr(demo, "get_settings", lambda: _S())
    with pytest.raises(SystemExit):
        demo.main(["--reset"])
