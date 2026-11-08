"""Pencocokan aturan: subset Sigma + agregasi threshold (PRD FR-102)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.event import Event


def event_field(event: Event, key: str) -> Any:
    """Ambil nilai field event. `raw.<x>` membaca dari muatan mentah."""
    if key.startswith("raw."):
        return (event.raw or {}).get(key[4:])
    return getattr(event, key, None)


def _match_value(actual: Any, expected: Any, *, contains: bool) -> bool:
    if isinstance(expected, list):
        return any(_match_value(actual, e, contains=contains) for e in expected)
    if actual is None:
        return False
    if contains:
        return str(expected).lower() in str(actual).lower()
    return str(actual) == str(expected)


def sigma_match(selection: dict[str, Any], event: Event) -> bool:
    """True bila SEMUA kriteria selection cocok (AND). Mendukung modifier `|contains`."""
    for raw_key, expected in selection.items():
        contains = raw_key.endswith("|contains")
        key = raw_key[:-9] if contains else raw_key
        if not _match_value(event_field(event, key), expected, contains=contains):
            return False
    return True


def column_equality_filter(flt: dict[str, Any]) -> dict[str, Any]:
    """Pisahkan filter yang bisa jadi where-clause kolom (nilai skalar, bukan raw.)."""
    return {
        k: v for k, v in flt.items()
        if not k.startswith("raw.") and not isinstance(v, (list, dict))
    }


def densest_window(
    timestamps: list[datetime], window_seconds: int, threshold: int
) -> tuple[int, int] | None:
    """Two-pointer: cari jendela berisi >= threshold event.

    Returns (index_awal, index_akhir_inklusif) pada list terurut, atau None.
    """
    n = len(timestamps)
    if n < threshold:
        return None
    left = 0
    for right in range(n):
        while (timestamps[right] - timestamps[left]).total_seconds() > window_seconds:
            left += 1
        if right - left + 1 >= threshold:
            return left, right
    return None
