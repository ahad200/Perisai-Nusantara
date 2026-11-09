"""Paket pelaporan & dashboard (M9, PRD §8.6 + §C.3).

- `metrics`  : metrik Situasi (COP) & KPI Eksekutif.
- `coverage` : coverage ATT&CK terhadap teknik prioritas + gap analysis.
- `service`  : ELANG-6 Reporter (template deterministik) — generate/approve/jadwal.
- `pdf`      : penulis PDF tanpa dependensi (FR-601 ekspor PDF).
"""
from app.reports.service import (
    approve_report,
    generate_report,
    render_report_pdf,
    run_due_schedules,
)

__all__ = [
    "generate_report",
    "approve_report",
    "run_due_schedules",
    "render_report_pdf",
]
