"""Grounding klaim LLM (PRD §11 halusinasi, FR-405): setiap klaim WAJIB merujuk
ID bukti (EVT-/ALERT-/IOC-) yang benar-benar ada di konteks. Klaim tanpa rujukan
valid ditandai dan tidak boleh ditampilkan sebagai fakta.
"""
from __future__ import annotations

import re

_REF_RE = re.compile(r"\b(?:EVT|ALERT|IOC)-\d+\b")


def extract_refs(text: str) -> list[str]:
    return _REF_RE.findall(text or "")


def filter_refs(refs: list[str], allowed: set[str]) -> tuple[list[str], list[str]]:
    """Pisahkan refs valid vs mengarang (tidak ada di konteks)."""
    valid, hallucinated = [], []
    for r in refs:
        (valid if r in allowed else hallucinated).append(r)
    return valid, hallucinated


def ground_claims(
    claims: list[dict], allowed: set[str]
) -> tuple[list[dict], list[str]]:
    """Validasi daftar klaim {text, refs}. Kembalikan (klaim_grounded, flags).

    - Ref yang mengarang dibuang dari klaim dan dicatat sebagai flag.
    - Klaim tanpa ref valid ditandai `grounded=False` (tetap disertakan agar
      transparan, tapi UI menandainya 'tak terverifikasi')."""
    grounded: list[dict] = []
    flags: list[str] = []
    for c in claims:
        text = str(c.get("text", "")).strip()
        if not text:
            continue
        declared = [str(r) for r in c.get("refs", [])]
        # Gabungkan ref yang dideklarasikan + yang tertulis di teks.
        declared += extract_refs(text)
        valid, hallu = filter_refs(list(dict.fromkeys(declared)), allowed)
        if hallu:
            flags.append(f"ref mengarang dibuang: {', '.join(sorted(set(hallu)))}")
        grounded.append({"text": text, "refs": valid, "grounded": bool(valid)})
    return grounded, flags
