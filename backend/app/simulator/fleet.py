"""Armada aset contoh (data simulasi) dengan kritikalitas K1/K2/K3 (PRD §7, §12).

Dipakai baseline & skenario serangan. `seed_assets` idempotent (lewati hostname
yang sudah ada) dan menulis AuditEntry per aset yang dibuat.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models.asset import Asset, Criticality


@dataclass(frozen=True, slots=True)
class FleetAsset:
    hostname: str
    ip: str
    segment: str
    owner: str
    criticality: Criticality
    tags: tuple[str, ...]


# Armada contoh: 2 K1 (misi-kritis), 3 K2 (penting), 6 K3 (umum).
FLEET: tuple[FleetAsset, ...] = (
    # K1 — misi-kritis (sistem komando & domain inti).
    FleetAsset("cmd-core-01", "10.10.1.10", "komando", "Pusdatin TNI", Criticality.K1, ("komando", "server")),
    FleetAsset("dc-root-01", "10.10.1.11", "inti", "Pusdatin TNI", Criticality.K1, ("domain-controller", "server")),
    # K2 — penting (server aplikasi pendukung & administrasi).
    FleetAsset("app-logistik-01", "10.10.2.20", "aplikasi", "Slog", Criticality.K2, ("aplikasi", "server")),
    FleetAsset("app-personel-01", "10.10.2.21", "aplikasi", "Spers", Criticality.K2, ("aplikasi", "server")),
    FleetAsset("db-pendukung-01", "10.10.2.22", "aplikasi", "Pusdatin TNI", Criticality.K2, ("database", "server")),
    # K3 — umum (endpoint pengguna).
    FleetAsset("ws-staff-01", "10.10.3.31", "pengguna", "Staf Umum", Criticality.K3, ("endpoint", "workstation")),
    FleetAsset("ws-staff-02", "10.10.3.32", "pengguna", "Staf Umum", Criticality.K3, ("endpoint", "workstation")),
    FleetAsset("ws-staff-03", "10.10.3.33", "pengguna", "Staf Intel", Criticality.K3, ("endpoint", "workstation")),
    FleetAsset("ws-staff-04", "10.10.3.34", "pengguna", "Staf Ops", Criticality.K3, ("endpoint", "workstation")),
    FleetAsset("ws-staff-05", "10.10.3.35", "pengguna", "Staf Logistik", Criticality.K3, ("endpoint", "workstation")),
    FleetAsset("ws-staff-06", "10.10.3.36", "pengguna", "Staf Personel", Criticality.K3, ("endpoint", "workstation")),
)


def seed_assets(db: Session, *, record_audit: bool = True) -> list[str]:
    """Tanam armada ke DB (idempotent). Mengembalikan daftar hostname yang baru dibuat."""
    created: list[str] = []
    for fa in FLEET:
        exists = db.execute(
            select(Asset.id).where(Asset.hostname == fa.hostname)
        ).scalar_one_or_none()
        if exists is not None:
            continue
        asset = Asset(
            hostname=fa.hostname,
            ip=fa.ip,
            segment=fa.segment,
            owner=fa.owner,
            criticality=fa.criticality.value,
            tags=list(fa.tags),
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        created.append(fa.hostname)
        if record_audit:
            audit.record(
                db,
                action="asset.create",
                actor_type="system",
                actor_id="simulator",
                object_type="asset",
                object_id=str(asset.id),
                payload={"hostname": asset.hostname, "criticality": asset.criticality, "seed": True},
            )
    return created
