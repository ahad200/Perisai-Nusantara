"""RBAC: role, permission, dan pemetaannya (PRD §3).

Modul ini murni (tanpa FastAPI) agar bebas dari import melingkar. Dependency
penegak izin ada di `app/api/deps.py`.

Model 4-role (konsolidasi dari 9 role awal) menjaga **empat pilar pemisahan tugas**:
eksekusi (`operator`) ⟂ persetujuan (`commander`) ⟂ validasi atribusi (`intel`)
⟂ audit (`auditor`). Prinsip:
- `operator` menjalankan aksi (playbook, deteksi, insiden) tapi **tidak bisa
  menyetujui** aksinya sendiri.
- `commander` menyetujui approval SOAR + break-glass dan mengelola platform
  (user/aset/aturan/laporan), tapi **tidak mengeksekusi** playbook.
- `intel` satu-satunya yang boleh memvalidasi hipotesis atribusi.
- `auditor` read-only; tidak ada role (termasuk commander) yang bisa
  mengubah/menghapus audit — audit immutable (tak ada endpoint mutasi sama sekali).
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    OPERATOR = "operator"      # SOC end-to-end: simulasi→deteksi→triase→insiden→eksekusi playbook→agen
    COMMANDER = "commander"    # supervisi + admin: approval SOAR/break-glass, laporan, kelola user/aset/aturan
    INTEL = "intel"            # threat intel + validasi atribusi (ELANG-3)
    AUDITOR = "auditor"        # read-only + verifikasi hash chain


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
    SOAR_READ = "soar:read"        # lihat playbook, run, approval, notifikasi
    SOAR_EXECUTE = "soar:execute"  # jalankan playbook, rollback (ELANG-4, operator)
    SOAR_APPROVE = "soar:approve"  # setujui/tolak approval (sesuai tier)
    SOAR_MANAGE = "soar:manage"    # seed playbook (admin), break-glass (commander)
    DASHBOARD_READ = "dashboard:read"  # situasi (COP), eksekutif, coverage ATT&CK
    REPORT_READ = "report:read"        # lihat & unduh laporan (PDF)
    REPORT_GENERATE = "report:generate"  # hasilkan laporan (ELANG-6 template)
    REPORT_APPROVE = "report:approve"    # setujui laporan sebelum kirim eksternal
    REPORT_MANAGE = "report:manage"      # kelola jadwal laporan
    AGENT_RUN = "agent:run"              # jalankan agen LLM (ELANG-2/3/6) — mengusulkan
    ATTRIBUTION_READ = "attribution:read"      # lihat hipotesis atribusi
    ATTRIBUTION_VALIDATE = "attribution:validate"  # label Tervalidasi (hanya role intel)


# Izin yang dimiliki **semua** role SOC: melihat inventaris aset, event, & intel.
_SOC_BASE = frozenset(
    {
        Permission.USER_READ,
        Permission.ASSET_READ,
        Permission.EVENT_READ,
        Permission.INTEL_READ,
        Permission.ALERT_READ,
        Permission.INCIDENT_READ,
        Permission.SOAR_READ,
        # Semua role SOC boleh melihat dashboard Situasi/Eksekutif/Coverage & laporan.
        Permission.DASHBOARD_READ,
        Permission.REPORT_READ,
        # Semua role SOC boleh melihat hipotesis atribusi (read-only).
        Permission.ATTRIBUTION_READ,
    }
)

# Pemetaan role -> himpunan izin. Sengaja eksplisit (bukan hierarki implisit)
# agar pemisahan tugas mudah diaudit.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    # OPERATOR — kerja tangan SOC end-to-end. MENGEKSEKUSI, tapi tidak menyetujui.
    Role.OPERATOR: _SOC_BASE
    | {
        Permission.SIM_RUN,          # pembangkit skenario (gabungan purple team)
        Permission.ALERT_TRIAGE,
        Permission.DETECT_RUN,
        Permission.DETECT_MANAGE,
        Permission.INCIDENT_MANAGE,
        Permission.SOAR_EXECUTE,     # jalankan/rollback playbook (ELANG-4)
        Permission.AGENT_RUN,        # jalankan agen LLM (ELANG-2/3/6)
        Permission.REPORT_GENERATE,
    },
    # COMMANDER — supervisi + administrasi platform. MENYETUJUI, tapi tidak mengeksekusi.
    Role.COMMANDER: _SOC_BASE
    | {
        Permission.AUDIT_READ,
        Permission.AUDIT_VERIFY,
        Permission.USER_CREATE,
        Permission.USER_MANAGE,
        Permission.ASSET_MANAGE,
        Permission.ALERT_TRIAGE,
        Permission.DETECT_MANAGE,
        Permission.INCIDENT_MANAGE,
        Permission.SOAR_APPROVE,     # setujui/tolak approval (satu-satunya penyetuju)
        Permission.SOAR_MANAGE,      # seed playbook + break-glass (§7 no.3)
        Permission.REPORT_GENERATE,
        Permission.REPORT_APPROVE,
        Permission.REPORT_MANAGE,
        Permission.AGENT_RUN,
    },
    # INTEL — threat intel + atribusi. Satu-satunya yang memvalidasi atribusi (§6).
    Role.INTEL: _SOC_BASE
    | {Permission.INTEL_MANAGE, Permission.AGENT_RUN, Permission.ATTRIBUTION_VALIDATE},
    # AUDITOR — read-only (pemisahan tugas): boleh membaca + verifikasi, tak boleh mengubah.
    Role.AUDITOR: _SOC_BASE | {Permission.AUDIT_READ, Permission.AUDIT_VERIFY},
}


def permissions_for(role: Role | str) -> frozenset[Permission]:
    try:
        role = Role(role)
    except ValueError:
        return frozenset()  # role tak dikenal (mis. data lama) → tanpa izin
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: Role | str, permission: Permission) -> bool:
    return permission in permissions_for(role)
