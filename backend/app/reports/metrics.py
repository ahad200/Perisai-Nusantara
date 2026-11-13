"""Metrik dashboard (PRD §C.3): Situasi (COP) & Eksekutif.

Semua angka dihitung deterministik dari data platform (tanpa egress, §A.5 no.5).
Definisi KPI di sini adalah penyederhanaan prototipe (dijelaskan di docstring tiap
fungsi) — bukan definisi final operasional.

KPI setiap angka wajib punya pembanding (PRD §C.5): fungsi eksekutif mengembalikan
nilai periode ini + periode sebelumnya + target bila ada.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertStatus
from app.models.asset import Asset, resolve_criticality
from app.models.detection import SEVERITY_RANK
from app.models.event import Event
from app.models.incident import Incident, IncidentStatus, OPEN_INCIDENT_STATUSES
from app.models.soar import Approval, ApprovalStatus
from app.reports import coverage as coverage_mod

_SEVERITIES = ["critical", "high", "medium", "low"]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


# --------------------------------------------------------------------------- #
# Situasi (Common Operating Picture)                                          #
# --------------------------------------------------------------------------- #
def situasi_snapshot(db: Session, *, now: datetime | None = None) -> dict:
    """Postur operasional saat ini: menjawab "apakah ada yang butuh tindakan
    saya sekarang?" (PRD §C.3)."""
    now = now or _now()
    since_24h = now - timedelta(hours=24)

    # Insiden aktif per severity.
    inc_rows = db.execute(
        select(Incident.severity, func.count(Incident.id))
        .where(Incident.status.in_(tuple(OPEN_INCIDENT_STATUSES)))
        .group_by(Incident.severity)
    ).all()
    inc_by_sev = {s: 0 for s in _SEVERITIES}
    for sev, n in inc_rows:
        inc_by_sev[sev] = int(n)
    active_incidents = sum(inc_by_sev.values())

    # Approval tertunda (butuh keputusan manusia).
    pending_approvals = int(
        db.execute(
            select(func.count(Approval.id)).where(Approval.status == ApprovalStatus.PENDING.value)
        ).scalar()
        or 0
    )

    # Alert baru (belum ditriase) — beban antrian.
    open_alerts = int(
        db.execute(
            select(func.count(Alert.id)).where(
                Alert.status.in_((AlertStatus.NEW.value, AlertStatus.ASSIGNED.value, AlertStatus.ESCALATED.value))
            )
        ).scalar()
        or 0
    )

    posture = _posture(inc_by_sev, pending_approvals)

    return {
        "generated_at": now.isoformat(),
        "posture": posture,
        "active_incidents": active_incidents,
        "incidents_by_severity": inc_by_sev,
        "pending_approvals": pending_approvals,
        "open_alerts": open_alerts,
        "trend_24h": _trend_hourly(db, since=since_24h, now=now),
        "data_sources": _data_source_health(db, now=now),
        "segments": _segment_map(db),
    }


def _posture(inc_by_sev: dict[str, int], pending_approvals: int) -> str:
    """Postur agregat: critical/elevated/guarded/normal."""
    if inc_by_sev.get("critical", 0) > 0:
        return "critical"
    if inc_by_sev.get("high", 0) > 0 or pending_approvals > 0:
        return "elevated"
    if inc_by_sev.get("medium", 0) > 0:
        return "guarded"
    return "normal"


def _trend_hourly(db: Session, *, since: datetime, now: datetime) -> list[dict]:
    """Jumlah alert per jam selama 24 jam terakhir (bucket per jam)."""
    rows = db.execute(
        select(Alert.created_at).where(Alert.created_at >= since)
    ).all()
    buckets = {i: 0 for i in range(24)}
    for (ts,) in rows:
        ts = _as_naive(ts)
        if ts is None:
            continue
        hours_ago = int((now - ts).total_seconds() // 3600)
        idx = 23 - hours_ago
        if 0 <= idx <= 23:
            buckets[idx] += 1
    base = now - timedelta(hours=23)
    return [
        {"hour": (base + timedelta(hours=i)).strftime("%H:00"), "alerts": buckets[i]}
        for i in range(24)
    ]


def _data_source_health(db: Session, *, now: datetime) -> list[dict]:
    """Kesehatan sumber data: event terakhir & jeda per `source_type`.

    Jeda dihitung relatif terhadap event TERBARU di seluruh sistem (bukan jam
    dinding), agar bermakna pada data simulasi historis. `stale` bila jeda sumber
    > 6 jam di belakang sumber paling baru."""
    latest_overall = _as_naive(
        db.execute(select(func.max(Event.ts))).scalar()
    )
    rows = db.execute(
        select(Event.source_type, func.count(Event.id), func.max(Event.ts)).group_by(Event.source_type)
    ).all()
    out: list[dict] = []
    for source, n, last in sorted(rows, key=lambda r: r[0]):
        last = _as_naive(last)
        lag_h = None
        healthy = True
        if latest_overall and last:
            lag_h = round((latest_overall - last).total_seconds() / 3600, 1)
            healthy = lag_h <= 6
        out.append(
            {
                "source": source,
                "events": int(n),
                "last_event_at": last.isoformat() if last else None,
                "lag_hours": lag_h,
                "status": "ok" if healthy else "stale",
            }
        )
    return out


_CRIT_RANK = {"K1": 3, "K2": 2, "K3": 1}


def _segment_map(db: Session) -> list[dict]:
    """Peta segmen jaringan: aset per segmen + kritikalitas + insiden aktif + host.

    Segmen diurutkan dari kritikalitas tertinggi (segmen ber-K1 dulu), lalu nama —
    berbasis data, bukan daftar nama segmen yang di-hardcode. Kritikalitas kosong
    diperlakukan K1 (fail-safe, §A.5 no.6).
    """
    seg: dict[str, dict] = {}
    host_idx: dict[int, dict] = {}

    def _seg(name: str | None) -> dict:
        return seg.setdefault(name or "(tak tersegmen)", {
            "assets": 0, "K1": 0, "K2": 0, "K3": 0,
            "active_incidents": 0, "max_severity": None, "hosts": [],
        })

    for a in db.execute(select(Asset).order_by(Asset.hostname.asc())).scalars().all():
        crit = resolve_criticality(a.criticality).value
        s = _seg(a.segment)
        s["assets"] += 1
        s[crit] += 1
        h = {
            "asset_id": a.id, "hostname": a.hostname, "ip": a.ip, "criticality": crit,
            "active_incidents": 0, "max_severity": None, "incident_id": None,
        }
        s["hosts"].append(h)
        host_idx[a.id] = h

    # Insiden aktif per segmen & host (lewat aset).
    inc_rows = db.execute(
        select(Asset.id, Asset.segment, Incident.id, Incident.severity)
        .join(Incident, Incident.asset_id == Asset.id)
        .where(Incident.status.in_(tuple(OPEN_INCIDENT_STATUSES)))
    ).all()
    for asset_id, segment, inc_id, sev in inc_rows:
        for target in (_seg(segment), host_idx.get(asset_id)):
            if target is None:
                continue
            target["active_incidents"] += 1
            cur = target["max_severity"]
            if cur is None or SEVERITY_RANK.get(sev, 0) > SEVERITY_RANK.get(cur, 0):
                target["max_severity"] = sev
                if "incident_id" in target:
                    target["incident_id"] = inc_id  # insiden paling parah di host

    def _seg_crit(v: dict) -> str:
        return next((k for k in ("K1", "K2", "K3") if v[k]), "K3")

    out = [
        {"segment": name, **v, "max_criticality": _seg_crit(v)}
        for name, v in seg.items()
    ]
    out.sort(key=lambda r: (-_CRIT_RANK[r["max_criticality"]], r["segment"]))
    return out


# --------------------------------------------------------------------------- #
# Eksekutif (KPI)                                                             #
# --------------------------------------------------------------------------- #
def _mean_minutes(deltas: list[float]) -> float | None:
    return round(sum(deltas) / len(deltas) / 60.0, 1) if deltas else None


def _mttd_minutes(db: Session, *, start: datetime, end: datetime) -> tuple[float | None, int]:
    """MTTD (prototipe): rata-rata (alert.created_at − first_event_ts) untuk alert
    yang dibuat pada periode. Proksi seberapa cepat alert muncul setelah event
    penyebab paling awal."""
    rows = db.execute(
        select(Alert.created_at, Alert.first_event_ts).where(
            Alert.created_at >= start, Alert.created_at < end
        )
    ).all()
    deltas = []
    for created, first in rows:
        created, first = _as_naive(created), _as_naive(first)
        if created and first and created >= first:
            deltas.append((created - first).total_seconds())
    return _mean_minutes(deltas), len(deltas)


def _mttr_minutes(db: Session, *, start: datetime, end: datetime) -> tuple[float | None, int]:
    """MTTR (prototipe): rata-rata (updated_at − created_at) untuk insiden yang
    berstatus `closed` dan terakhir diperbarui pada periode. Tanpa kolom closed_at
    khusus, updated_at saat penutupan dipakai sebagai proksi waktu respons."""
    rows = db.execute(
        select(Incident.created_at, Incident.updated_at).where(
            Incident.status == IncidentStatus.CLOSED.value,
            Incident.updated_at >= start,
            Incident.updated_at < end,
        )
    ).all()
    deltas = []
    for created, updated in rows:
        created, updated = _as_naive(created), _as_naive(updated)
        if created and updated and updated >= created:
            deltas.append((updated - created).total_seconds())
    return _mean_minutes(deltas), len(deltas)


def _fp_rate(db: Session, *, start: datetime, end: datetime) -> tuple[float | None, int, int]:
    """FP rate: alert ditutup sebagai false-positive / total alert pada periode."""
    total = int(
        db.execute(
            select(func.count(Alert.id)).where(Alert.created_at >= start, Alert.created_at < end)
        ).scalar()
        or 0
    )
    fp = int(
        db.execute(
            select(func.count(Alert.id)).where(
                Alert.created_at >= start,
                Alert.created_at < end,
                Alert.status == AlertStatus.CLOSED_FP.value,
            )
        ).scalar()
        or 0
    )
    rate = round(100 * fp / total, 1) if total else None
    return rate, fp, total


def executive_kpis(db: Session, *, days: int = 30, now: datetime | None = None) -> dict:
    """KPI eksekutif (FR-603): MTTD, MTTR, FP rate, coverage + pembanding periode
    sebelumnya + tren harian."""
    now = now or _now()
    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)

    mttd, mttd_n = _mttd_minutes(db, start=start, end=now)
    mttd_prev, _ = _mttd_minutes(db, start=prev_start, end=start)
    mttr, mttr_n = _mttr_minutes(db, start=start, end=now)
    mttr_prev, _ = _mttr_minutes(db, start=prev_start, end=start)
    fp, fp_count, fp_total = _fp_rate(db, start=start, end=now)
    fp_prev, _, _ = _fp_rate(db, start=prev_start, end=start)
    cov = coverage_mod.coverage_matrix(db)

    incidents_total = int(
        db.execute(
            select(func.count(Incident.id)).where(Incident.created_at >= start, Incident.created_at < now)
        ).scalar()
        or 0
    )
    incidents_prev = int(
        db.execute(
            select(func.count(Incident.id)).where(
                Incident.created_at >= prev_start, Incident.created_at < start
            )
        ).scalar()
        or 0
    )

    return {
        "generated_at": now.isoformat(),
        "window_days": days,
        "kpis": {
            "mttd_minutes": {"value": mttd, "prev": mttd_prev, "sample": mttd_n, "better": "lower"},
            "mttr_minutes": {"value": mttr, "prev": mttr_prev, "sample": mttr_n, "better": "lower"},
            "fp_rate_pct": {
                "value": fp, "prev": fp_prev, "count": fp_count, "total": fp_total, "better": "lower",
            },
            "coverage_pct": {
                "value": cov["coverage_pct"], "prev": None, "target": 50.0, "better": "higher",
            },
            "incidents": {"value": incidents_total, "prev": incidents_prev, "better": "lower"},
        },
        "trend_daily": _trend_daily(db, start=start, now=now, days=days),
        "key_incidents": _key_incidents(db, start=start, now=now),
    }


def _trend_daily(db: Session, *, start: datetime, now: datetime, days: int) -> list[dict]:
    """Tren insiden & alert per hari selama jendela."""
    inc_rows = db.execute(
        select(Incident.created_at).where(Incident.created_at >= start, Incident.created_at < now)
    ).all()
    alert_rows = db.execute(
        select(Alert.created_at).where(Alert.created_at >= start, Alert.created_at < now)
    ).all()

    inc_buckets = {i: 0 for i in range(days)}
    alert_buckets = {i: 0 for i in range(days)}
    start_day = start.date()

    def _bucket(ts, buckets):
        ts = _as_naive(ts)
        if ts is None:
            return
        idx = (ts.date() - start_day).days
        if 0 <= idx < days:
            buckets[idx] += 1

    for (ts,) in inc_rows:
        _bucket(ts, inc_buckets)
    for (ts,) in alert_rows:
        _bucket(ts, alert_buckets)

    return [
        {
            "date": (start_day + timedelta(days=i)).isoformat(),
            "incidents": inc_buckets[i],
            "alerts": alert_buckets[i],
        }
        for i in range(days)
    ]


def _key_incidents(db: Session, *, start: datetime, now: datetime, limit: int = 8) -> list[dict]:
    """Insiden penting pada periode: diurutkan severity lalu jumlah alert."""
    rows = db.execute(
        select(Incident)
        .where(Incident.created_at >= start, Incident.created_at < now)
        .order_by(Incident.created_at.desc())
    ).scalars().all()
    rows = sorted(
        rows,
        key=lambda i: (SEVERITY_RANK.get(i.severity, 0), i.alert_count),
        reverse=True,
    )[:limit]
    return [
        {
            "incident_code": i.incident_code,
            "title": i.title,
            "severity": i.severity,
            "status": i.status,
            "host": i.host,
            "alert_count": i.alert_count,
            "techniques": [t.get("technique") if isinstance(t, dict) else t for t in (i.techniques or [])],
            "created_at": _as_naive(i.created_at).isoformat() if i.created_at else None,
        }
        for i in rows
    ]
