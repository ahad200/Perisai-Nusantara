"""Impor STIX 2.1 bundle (PRD FR-201). Transfer satu arah — tidak ada TAXII keluar.

Parser pola bersifat **pragmatis** (prototipe): mengekstrak pola perbandingan umum
(`[ipv4-addr:value = '...']`, hash berkas, domain, url, email). Pola STIX kompleks
(ekspresi bertingkat, operator selain '=') belum didukung penuh.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models.ioc import IoC, IoCStatus, IoCType, Tlp, as_naive, utcnow_naive

# ID marking-definition TLP standar (STIX 2.1 / TLP 1.0).
_TLP_MARKINGS = {
    "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9": Tlp.WHITE,
    "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da": Tlp.GREEN,
    "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82": Tlp.AMBER,
    "marking-definition--5e57c739-391a-4eb3-b6be-7d15ca92d5ed": Tlp.RED,
}

# Pola: <obj-type>:<property-path> = '<value>'
_PATTERN_RE = re.compile(r"([a-z0-9][a-z0-9-]*):([^\s=]+)\s*=\s*'([^']*)'", re.IGNORECASE)

_OBJ_TO_TYPE = {
    "ipv4-addr": IoCType.IP,
    "ipv6-addr": IoCType.IPV6,
    "domain-name": IoCType.DOMAIN,
    "url": IoCType.URL,
    "email-addr": IoCType.EMAIL,
}


def _hash_type(prop_path: str) -> IoCType:
    p = prop_path.lower()
    if "sha-256" in p or "sha256" in p:
        return IoCType.SHA256
    if "sha-1" in p or "sha1" in p:
        return IoCType.SHA1
    if "md5" in p:
        return IoCType.MD5
    return IoCType.OTHER


def parse_pattern(pattern: str) -> list[tuple[IoCType, str]]:
    """Ekstrak pasangan (tipe, nilai) dari pola STIX. Mengabaikan AND/OR/kurung."""
    out: list[tuple[IoCType, str]] = []
    for obj_type, prop, value in _PATTERN_RE.findall(pattern or ""):
        obj_type = obj_type.lower()
        if obj_type == "file":
            out.append((_hash_type(prop), value))
        elif obj_type in _OBJ_TO_TYPE:
            out.append((_OBJ_TO_TYPE[obj_type], value))
        # obj-type lain diabaikan (prototipe)
    return out


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return as_naive(dt) if dt.tzinfo else dt


def _resolve_tlp(obj: dict[str, Any], default: Tlp) -> Tlp:
    for ref in obj.get("object_marking_refs", []) or []:
        if ref in _TLP_MARKINGS:
            return _TLP_MARKINGS[ref]
    return default


def import_bundle(
    db: Session,
    bundle: dict[str, Any],
    *,
    default_source: str = "STIX import",
    default_tlp: Tlp = Tlp.AMBER,
    actor_id: str | None = "stix-import",
    actor_type: str = "system",
    record_audit: bool = True,
) -> dict[str, Any]:
    """Impor indikator dari bundle STIX. Idempotent per (tipe, nilai).

    Returns: {created, updated, skipped, errors, total_indicators}.
    """
    if not isinstance(bundle, dict) or bundle.get("type") != "bundle":
        raise ValueError("Bukan STIX bundle yang valid (type != 'bundle')")

    objects = bundle.get("objects", [])
    indicators = [o for o in objects if isinstance(o, dict) and o.get("type") == "indicator"]
    now = utcnow_naive()
    created = updated = skipped = 0
    errors: list[str] = []

    for ind in indicators:
        pairs = parse_pattern(ind.get("pattern", ""))
        if not pairs:
            skipped += 1
            errors.append(f"pola tak terbaca: {ind.get('id', '?')}")
            continue

        tlp = _resolve_tlp(ind, default_tlp)
        first_seen = _parse_time(ind.get("valid_from") or ind.get("created")) or now
        expires = _parse_time(ind.get("valid_until"))
        confidence = int(ind.get("confidence", 50))
        labels = list(ind.get("labels", []) or [])
        desc = ind.get("name") or ind.get("description") or ""
        stix_id = ind.get("id")
        status = (
            IoCStatus.EXPIRED.value
            if expires is not None and expires <= now
            else IoCStatus.ACTIVE.value
        )

        for ioc_type, value in pairs:
            existing = db.execute(
                select(IoC).where(IoC.type == ioc_type.value, IoC.value == value)
            ).scalar_one_or_none()
            if existing is None:
                db.add(IoC(
                    type=ioc_type.value, value=value, source=default_source, tlp=tlp.value,
                    confidence=confidence, status=status, first_seen=first_seen, last_seen=now,
                    expires_at=expires, description=desc[:512], tags=labels, stix_id=stix_id,
                ))
                created += 1
            else:
                existing.last_seen = now
                existing.confidence = max(existing.confidence, confidence)
                existing.expires_at = expires or existing.expires_at
                existing.source = default_source
                existing.stix_id = stix_id or existing.stix_id
                if labels:
                    existing.tags = sorted(set(existing.tags) | set(labels))
                # Status whitelist/FP (keputusan analis) tidak ditimpa impor.
                if existing.status not in (
                    IoCStatus.WHITELISTED.value, IoCStatus.FALSE_POSITIVE.value
                ):
                    existing.status = status
                updated += 1

    db.commit()

    result = {
        "created": created, "updated": updated, "skipped": skipped,
        "errors": errors, "total_indicators": len(indicators),
    }
    if record_audit:
        audit.record(
            db,
            action="ioc.import",
            actor_type=actor_type,
            actor_id=actor_id,
            object_type="stix_bundle",
            object_id=bundle.get("id"),
            payload={k: v for k, v in result.items() if k != "errors"} | {"source": default_source},
        )
    return result
