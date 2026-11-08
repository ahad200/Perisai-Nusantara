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


# Pemetaan role -> himpunan izin. Sengaja eksplisit (bukan hierarki implisit)
# agar pemisahan tugas mudah diaudit.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.COMMANDER: frozenset(
        {Permission.USER_READ, Permission.AUDIT_READ, Permission.AUDIT_VERIFY}
    ),
    Role.PLATFORM_ADMIN: frozenset(
        {
            Permission.USER_READ,
            Permission.USER_CREATE,
            Permission.USER_MANAGE,
            Permission.AUDIT_READ,
            Permission.AUDIT_VERIFY,
        }
    ),
    Role.AUDITOR: frozenset(
        {Permission.USER_READ, Permission.AUDIT_READ, Permission.AUDIT_VERIFY}
    ),
    Role.ANALYST_T1: frozenset({Permission.USER_READ}),
    Role.ANALYST_T2: frozenset({Permission.USER_READ}),
    Role.ANALYST_T3: frozenset({Permission.USER_READ}),
    Role.TI_OFFICER: frozenset({Permission.USER_READ}),
    Role.RESPONDER: frozenset({Permission.USER_READ}),
    Role.PURPLE_TEAM: frozenset({Permission.USER_READ}),
}


def permissions_for(role: Role | str) -> frozenset[Permission]:
    role = Role(role)
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: Role | str, permission: Permission) -> bool:
    return permission in permissions_for(role)
