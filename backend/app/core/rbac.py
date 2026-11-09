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
    INTEL_READ = "intel:read"
    INTEL_MANAGE = "intel:manage"  # kelola IoC, impor STIX, siklus hidup
    ALERT_READ = "alert:read"
    ALERT_TRIAGE = "alert:triage"  # assign / eskalasi / tutup FP
    DETECT_RUN = "detect:run"      # jalankan mesin deteksi
    DETECT_MANAGE = "detect:manage"  # kelola/seed aturan deteksi
    INCIDENT_READ = "incident:read"
    INCIDENT_MANAGE = "incident:manage"  # korelasi, status, penugasan, catatan kasus


# Izin yang dimiliki **semua** role SOC: melihat inventaris aset, event, & intel.
_SOC_BASE = frozenset(
    {
        Permission.USER_READ,
        Permission.ASSET_READ,
        Permission.EVENT_READ,
        Permission.INTEL_READ,
        Permission.ALERT_READ,
        Permission.INCIDENT_READ,
    }
)

# Izin triase alert: dimiliki analis T1–T3 (operasi antrian alert).
_ANALYST_TRIAGE = frozenset({Permission.ALERT_TRIAGE, Permission.DETECT_RUN})

# Pemetaan role -> himpunan izin. Sengaja eksplisit (bukan hierarki implisit)
# agar pemisahan tugas mudah diaudit.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.COMMANDER: _SOC_BASE
    | {
        Permission.AUDIT_READ,
        Permission.AUDIT_VERIFY,
        Permission.ALERT_TRIAGE,
        Permission.INCIDENT_MANAGE,
    },
    Role.PLATFORM_ADMIN: _SOC_BASE
    | {
        Permission.USER_CREATE,
        Permission.USER_MANAGE,
        Permission.AUDIT_READ,
        Permission.AUDIT_VERIFY,
        Permission.ASSET_MANAGE,
        Permission.SIM_RUN,
        Permission.INTEL_MANAGE,
        Permission.ALERT_TRIAGE,
        Permission.DETECT_RUN,
        Permission.DETECT_MANAGE,
        Permission.INCIDENT_MANAGE,
    },
    # Auditor tetap read-only (pemisahan tugas): boleh membaca, tak boleh mengubah.
    Role.AUDITOR: _SOC_BASE | {Permission.AUDIT_READ, Permission.AUDIT_VERIFY},
    Role.ANALYST_T1: _SOC_BASE | _ANALYST_TRIAGE,
    # T2/T3 mengelola insiden (korelasi alert -> kasus, siklus respons).
    Role.ANALYST_T2: _SOC_BASE | _ANALYST_TRIAGE | {Permission.INCIDENT_MANAGE},
    Role.ANALYST_T3: _SOC_BASE
    | _ANALYST_TRIAGE
    | {Permission.DETECT_MANAGE, Permission.INCIDENT_MANAGE},
    # Threat Intel Officer: kelola IoC, impor STIX, siklus hidup (PRD §3).
    Role.TI_OFFICER: _SOC_BASE | {Permission.INTEL_MANAGE},
    # Responder: pemilik alami penanganan insiden (containment).
    Role.RESPONDER: _SOC_BASE | {Permission.INCIDENT_MANAGE},
    # Purple team menjalankan simulasi serangan (data simulasi).
    Role.PURPLE_TEAM: _SOC_BASE | {Permission.SIM_RUN, Permission.DETECT_RUN},
}


def permissions_for(role: Role | str) -> frozenset[Permission]:
    role = Role(role)
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: Role | str, permission: Permission) -> bool:
    return permission in permissions_for(role)
