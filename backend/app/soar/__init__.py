"""SOAR Engine (PRD M8): playbook, Matriks Otonomi, approval/timeout/eskalasi,
rollback, dry-run, adapter mock, notifikasi in-app.

Hanya modul ini (`app/soar/`) yang boleh memanggil adapter eksekusi (§A.5 no.1);
semua adapter mock (§A.5 no.8). Keputusan auto/approval dihitung Matriks Otonomi
dari konfigurasi (§A.5 no.2).
"""
from app.soar.approvals import process_timeouts, resolve_approval
from app.soar.engine import rollback_run, run_playbook
from app.soar.playbooks import seed_playbooks

__all__ = ["run_playbook", "rollback_run", "resolve_approval", "process_timeouts", "seed_playbooks"]
