"""Notifikasi in-app (PRD FR-303: approver diberi tahu ≤ 1 menit).

Prototipe: notifikasi disimpan ke tabel `notifications` dan ditampilkan di UI
(bell). Tanpa egress jaringan (§A.5 no.5) — murni in-app.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.soar import BreakGlass, Notification


def notify(
    db: Session, *, recipient_role: str, kind: str, title: str, body: str = "",
    ref_type: str | None = None, ref_id: int | None = None, commit: bool = True,
) -> Notification:
    n = Notification(
        recipient_role=recipient_role, kind=kind, title=title, body=body,
        ref_type=ref_type, ref_id=ref_id,
    )
    db.add(n)
    if commit:
        db.commit()
        db.refresh(n)
    return n


def active_break_glass(db: Session, now: datetime | None = None) -> BreakGlass | None:
    """Mode break-glass yang masih aktif (belum kedaluwarsa), bila ada (§7 no.3)."""
    now = now or datetime.now(timezone.utc)
    # Bandingkan naif (DB menyimpan naif UTC di beberapa dialek).
    now_naive = now.replace(tzinfo=None)
    rows = db.execute(select(BreakGlass).order_by(BreakGlass.id.desc())).scalars().all()
    for bg in rows:
        exp = bg.expires_at
        exp = exp.replace(tzinfo=None) if exp.tzinfo else exp
        if exp > now_naive:
            return bg
    return None
