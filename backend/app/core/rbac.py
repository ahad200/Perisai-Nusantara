"""RBAC: role, permission, dan pemetaannya (PRD §3).

Modul ini murni (tanpa FastAPI) agar bebas dari import melingkar. Dependency
penegak izin ada di `app/api/deps.py`.

Prinsip pemisahan tugas (PRD §3):
- `auditor` read-only.
- Tidak ada role yang memiliki izin mengubah/menghapus audit (audit immutable —
  memang tidak ada endpoint mutasi audit sama sekali).
- `platform_admin` mengelola user tetapi tidak dapat menyentuh isi audit log.
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    COMMANDER = "commander"
    ANALYST_T1 = "analyst_t1"
    ANALYST_T2 = "analyst_t2"
    ANALYST_T3 = "analyst_t3"
    TI_OFFICER = "ti_officer"
    RESPONDER = "responder"
    PURPLE_TEAM = "purple_team"
    AUDITOR = "auditor"
    PLATFORM_ADMIN = "platform_admin"


class Permission(StrEnum):
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"
    AUDIT_VERIFY = "audit:verify"
    ASSET_READ = "asset:read"
    ASSET_MANAGE = "asset:manage"
    EVENT_READ = "event:read"
    SIM_RUN = "sim:run"  # menjalankan simulator (data simulasi) — non-prod


# Izin yang dimiliki **semua** role SOC: melihat inventaris aset & menjelajah event.
_SOC_BASE = frozenset(
    {Permission.USER_READ, Permission.ASSET_READ, Permission.EVENT_READ}
)

# Pemetaan role -> himpunan izin. Sengaja eksplisit (bukan hierarki implisit)
# agar pemisahan tugas mudah diaudit.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.COMMANDER: _SOC_BASE | {Permission.AUDIT_READ, Permission.AUDIT_VERIFY},
    Role.PLATFORM_ADMIN: _SOC_BASE
    | {
        Permission.USER_CREATE,
        Permission.USER_MANAGE,
        Permission.AUDIT_READ,
        Permission.AUDIT_VERIFY,
        Permission.ASSET_MANAGE,
        Permission.SIM_RUN,
    },
    # Auditor tetap read-only (pemisahan tugas): boleh membaca, tak boleh mengubah.
    Role.AUDITOR: _SOC_BASE | {Permission.AUDIT_READ, Permission.AUDIT_VERIFY},
    Role.ANALYST_T1: _SOC_BASE,
    Role.ANALYST_T2: _SOC_BASE,
    Role.ANALYST_T3: _SOC_BASE,
    Role.TI_OFFICER: _SOC_BASE,
    Role.RESPONDER: _SOC_BASE,
    # Purple team menjalankan simulasi serangan (data simulasi).
    Role.PURPLE_TEAM: _SOC_BASE | {Permission.SIM_RUN},
}


def permissions_for(role: Role | str) -> frozenset[Permission]:
    role = Role(role)
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: Role | str, permission: Permission) -> bool:
    return permission in permissions_for(role)
