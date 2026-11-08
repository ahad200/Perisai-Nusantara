"""Orkestrasi deteksi: jalankan aturan -> hasilkan/segarkan Alert (PRD M5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.detection.matcher import (
    column_equality_filter,
    densest_window,
    event_field,
    sigma_match,
)
from app.models.alert import Alert, AlertStatus
from app.models.asset import Asset
from app.models.detection import DetectionRule, RuleStatus, RuleType, Severity
from app.models.event import Event
from app.models.ioc import IoC, IoCStatus, IoCType

# Teknik ATT&CK diturunkan dari label IoC (untuk aturan tipe `ioc`).
_IOC_LABEL_TECHNIQUE = {
    "c2": ("T1071", "Application Layer Protocol", Severity.HIGH),
    "ransomware": ("T1486", "Data Encrypted for Impact", Severity.CRITICAL),
    "bruteforce": ("T1110", "Brute Force", Severity.HIGH),
    "scanner": ("T1595", "Active Scanning", Severity.MEDIUM),
}


@dataclass(slots=True)
class Candidate:
    dedup_key: str
    rule: DetectionRule
    severity: str
    technique: str | None
    technique_name: str | None
    host: str | None
    title: str
    explanation: str
    event_ids: list[int] = field(default_factory=list)
    first_ts: datetime | None = None
    last_ts: datetime | None = None


def _host_map(db: Session) -> dict[str, int]:
    return {h: i for h, i in db.execute(select(Asset.hostname, Asset.id)).all()}


def _query_events(db: Session, cols: dict[str, Any]) -> list[Event]:
    stmt = select(Event)
    for k, v in cols.items():
        stmt = stmt.where(getattr(Event, k) == v)
    return list(db.execute(stmt.order_by(Event.ts.asc())).scalars().all())


def _run_threshold(db: Session, rule: DetectionRule) -> list[Candidate]:
    c = rule.content
    flt, group_by = c.get("filter", {}), c.get("group_by", [])
    count, window = int(c.get("count", 10)), int(c.get("window_seconds", 900))
    events = _query_events(db, column_equality_filter(flt))

    groups: dict[tuple, list[Event]] = {}
    for e in events:
        key = tuple(str(event_field(e, g)) for g in group_by)
        groups.setdefault(key, []).append(e)

    out: list[Candidate] = []
    for key, evs in groups.items():
        evs.sort(key=lambda e: e.ts)
        win = densest_window([e.ts for e in evs], window, count)
        if win is None:
            continue
        lo, hi = win
        subset = evs[lo : hi + 1]
        gk = dict(zip(group_by, key))
        host = gk.get("host") or subset[0].host
        src = gk.get("src_ip", "?")
        out.append(Candidate(
            dedup_key=f"rule:{rule.rule_code}:" + "|".join(key),
            rule=rule, severity=rule.severity, technique=rule.technique,
            technique_name=rule.technique_name, host=host, title=rule.name,
            explanation=f"{len(subset)} event cocok (sumber {src}) dalam {window//60} menit.",
            event_ids=[e.id for e in subset], first_ts=subset[0].ts, last_ts=subset[-1].ts,
        ))
    return out


def _run_sigma(db: Session, rule: DetectionRule) -> list[Candidate]:
    sel = rule.content.get("selection", {})
    scalar_cols = {k: v for k, v in column_equality_filter(sel).items()}
    candidates = _query_events(db, scalar_cols)
    matched = [e for e in candidates if sigma_match(sel, e)]

    by_host: dict[str | None, list[Event]] = {}
    for e in matched:
        by_host.setdefault(e.host, []).append(e)

    out: list[Candidate] = []
    for host, evs in by_host.items():
        evs.sort(key=lambda e: e.ts)
        out.append(Candidate(
            dedup_key=f"rule:{rule.rule_code}:{host}",
            rule=rule, severity=rule.severity, technique=rule.technique,
            technique_name=rule.technique_name, host=host, title=rule.name,
            explanation=f"{len(evs)} event cocok aturan Sigma '{rule.rule_code}'.",
            event_ids=[e.id for e in evs], first_ts=evs[0].ts, last_ts=evs[-1].ts,
        ))
    return out


def _ioc_technique(tags: list[str]) -> tuple[str | None, str | None, str]:
    for tag in tags:
        if tag in _IOC_LABEL_TECHNIQUE:
            tech, name, sev = _IOC_LABEL_TECHNIQUE[tag]
            return tech, name, sev.value
    return None, None, Severity.MEDIUM.value


def _events_for_ioc(db: Session, ioc: IoC) -> list[Event]:
    t = ioc.type
    if t in (IoCType.IP.value, IoCType.IPV6.value):
        return list(db.execute(
            select(Event).where((Event.src_ip == ioc.value) | (Event.dst_ip == ioc.value))
        ).scalars().all())
    if t == IoCType.DOMAIN.value:
        rows = db.execute(select(Event).where(Event.source_type == "proxy")).scalars().all()
        return [e for e in rows if (e.raw or {}).get("dst_domain") == ioc.value]
    # hash/url/email: belum ada field event yang cocok di prototipe.
    return []


def _run_ioc(db: Session, rule: DetectionRule) -> list[Candidate]:
    iocs = db.execute(
        select(IoC).where(IoC.status == IoCStatus.ACTIVE.value)
    ).scalars().all()
    out: list[Candidate] = []
    for ioc in iocs:
        if not ioc.is_blockable():  # kedaluwarsa/whitelist tidak dipakai (FR-205)
            continue
        events = _events_for_ioc(db, ioc)
        if not events:
            continue
        tech, tech_name, sev = _ioc_technique(ioc.tags or [])
        by_host: dict[str | None, list[Event]] = {}
        for e in events:
            by_host.setdefault(e.host, []).append(e)
        for host, evs in by_host.items():
            evs.sort(key=lambda e: e.ts)
            out.append(Candidate(
                dedup_key=f"ioc:{ioc.id}:{host}",
                rule=rule, severity=sev, technique=tech, technique_name=tech_name,
                host=host, title=f"IoC {ioc.type}:{ioc.value}",
                explanation=f"{len(evs)} event menyentuh IoC {ioc.value} (TLP:{ioc.tlp}, sumber {ioc.source}).",
                event_ids=[e.id for e in evs], first_ts=evs[0].ts, last_ts=evs[-1].ts,
            ))
    return out


_RUNNERS = {
    RuleType.THRESHOLD.value: _run_threshold,
    RuleType.SIGMA.value: _run_sigma,
    RuleType.IOC.value: _run_ioc,
}


def run_detection(
    db: Session, *, actor_id: str | None = "detection", actor_type: str = "system",
    record_audit: bool = True,
) -> dict[str, Any]:
    """Jalankan semua aturan aktif. Idempotent (dedup_key). Return ringkasan."""
    rules = db.execute(
        select(DetectionRule).where(DetectionRule.status == RuleStatus.ENABLED.value)
    ).scalars().all()
    host_map = _host_map(db)

    candidates: list[Candidate] = []
    for rule in rules:
        runner = _RUNNERS.get(rule.type)
        if runner is not None:
            candidates.extend(runner(db, rule))

    created = updated = 0
    for c in candidates:
        existing = db.execute(
            select(Alert).where(Alert.dedup_key == c.dedup_key)
        ).scalar_one_or_none()
        if existing is None:
            db.add(Alert(
                rule_id=c.rule.id, rule_code=c.rule.rule_code, severity=c.severity,
                technique=c.technique, technique_name=c.technique_name,
                asset_id=host_map.get(c.host) if c.host else None, host=c.host,
                title=c.title, explanation=c.explanation, event_ids=c.event_ids,
                event_count=len(c.event_ids), status=AlertStatus.NEW.value,
                dedup_key=c.dedup_key, first_event_ts=c.first_ts, last_event_ts=c.last_ts,
            ))
            created += 1
        else:
            merged = sorted(set(existing.event_ids) | set(c.event_ids))
            existing.event_ids = merged
            existing.event_count = len(merged)
            if c.last_ts and (existing.last_event_ts is None or c.last_ts > existing.last_event_ts):
                existing.last_event_ts = c.last_ts
            updated += 1

    db.commit()

    result = {
        "rules_run": len(rules), "candidates": len(candidates),
        "created": created, "updated": updated,
    }
    if record_audit:
        audit.record(
            db, action="detection.run", actor_type=actor_type, actor_id=actor_id,
            object_type="detection", payload=result,
        )
    return result
