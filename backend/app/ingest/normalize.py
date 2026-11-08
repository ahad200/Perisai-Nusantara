"""Normalisasi event ke skema umum (ECS/OCSF-inspired).

Setiap sumber log punya bentuk `raw` berbeda; `normalize()` memetakannya ke
`NormalizedEvent` yang seragam. Fungsi ini **murni** (tanpa DB/IO) agar mudah diuji
dan dipakai ulang oleh ingest maupun simulator.

Menambah sumber baru = menambah satu fungsi di `_NORMALIZERS`. Sumber tak dikenal
tidak dibuang: dinormalisasi sebagai kategori `other` (fail-open untuk visibilitas,
bukan untuk keputusan).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class NormalizedEvent:
    ts: datetime
    source_type: str
    category: str  # authentication | network | file | process | other
    action: str
    outcome: str = "unknown"  # success | failure | unknown
    host: str | None = None
    user: str | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    dst_port: int | None = None
    bytes_out: int | None = None
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def _s(raw: dict[str, Any], key: str) -> str | None:
    val = raw.get(key)
    return str(val) if val is not None else None


def _i(raw: dict[str, Any], key: str) -> int | None:
    val = raw.get(key)
    return int(val) if val is not None else None


def _norm_auth(ts: datetime, raw: dict[str, Any]) -> NormalizedEvent:
    event = str(raw.get("event", "")).lower()
    outcome = "failure" if "fail" in event else "success"
    user = _s(raw, "user")
    host = _s(raw, "host")
    src = _s(raw, "src_ip")
    verb = "login_failed" if outcome == "failure" else "login_success"
    return NormalizedEvent(
        ts=ts, source_type="auth", category="authentication", action=verb,
        outcome=outcome, host=host, user=user, src_ip=src, raw=raw,
        message=f"{user or '?'}@{host or '?'} {verb} dari {src or '?'}",
    )


def _norm_firewall(ts: datetime, raw: dict[str, Any]) -> NormalizedEvent:
    action = str(raw.get("action", "allow")).lower()
    allowed = action in {"allow", "accept", "permit"}
    return NormalizedEvent(
        ts=ts, source_type="firewall", category="network",
        action="flow_allow" if allowed else "flow_deny",
        outcome="success" if allowed else "failure",
        host=_s(raw, "host"), src_ip=_s(raw, "src_ip"), dst_ip=_s(raw, "dst_ip"),
        dst_port=_i(raw, "dst_port"), bytes_out=_i(raw, "bytes"), raw=raw,
        message=f"{raw.get('src_ip','?')} -> {raw.get('dst_ip','?')}:{raw.get('dst_port','?')} {action}",
    )


def _norm_proxy(ts: datetime, raw: dict[str, Any]) -> NormalizedEvent:
    return NormalizedEvent(
        ts=ts, source_type="proxy", category="network", action="http_request",
        outcome="success", host=_s(raw, "host"), user=_s(raw, "user"),
        dst_ip=_s(raw, "dst_ip"), dst_port=_i(raw, "dst_port"),
        bytes_out=_i(raw, "bytes_out"), raw=raw,
        message=f"{raw.get('host','?')} -> {raw.get('dst_domain') or raw.get('dst_ip','?')}",
    )


def _norm_edr(ts: datetime, raw: dict[str, Any]) -> NormalizedEvent:
    op = str(raw.get("action", "process_start")).lower()
    if op in {"file_modify", "file_encrypt"}:
        category, verb = "file", "file_modify"
    else:
        category, verb = "process", "process_start"
    return NormalizedEvent(
        ts=ts, source_type="edr", category=category, action=verb,
        outcome="success", host=_s(raw, "host"), user=_s(raw, "user"), raw=raw,
        message=(
            f"{raw.get('process','?')} mengubah {raw.get('file_count','?')} berkas"
            if category == "file"
            else f"proses dimulai: {raw.get('process','?')}"
        ),
    )


_NORMALIZERS: dict[str, Callable[[datetime, dict[str, Any]], NormalizedEvent]] = {
    "auth": _norm_auth,
    "firewall": _norm_firewall,
    "proxy": _norm_proxy,
    "edr": _norm_edr,
}

# Sumber yang didukung normalisasi penuh (dipakai validasi & dokumentasi).
SUPPORTED_SOURCES = tuple(_NORMALIZERS)


def normalize(source_type: str, raw: dict[str, Any], ts: datetime) -> NormalizedEvent:
    """Normalisasi satu event. Sumber tak dikenal -> kategori `other`."""
    fn = _NORMALIZERS.get(source_type)
    if fn is None:
        return NormalizedEvent(
            ts=ts, source_type=source_type, category="other",
            action=str(raw.get("action", "unknown")), host=_s(raw, "host"), raw=raw,
            message=f"sumber tak dikenal: {source_type}",
        )
    return fn(ts, raw)
