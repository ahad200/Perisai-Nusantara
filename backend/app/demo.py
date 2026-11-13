"""Isi data demo lengkap dalam satu perintah (data simulasi, non-produksi).

    python -m app.demo            # isi data demo (aman dijalankan ulang)
    python -m app.demo --reset    # hapus SEMUA data lalu isi ulang (lingkungan demo saja)

Urutan: user demo per role → aset K1/K2/K3 → baseline 14 hari + 3 skenario serangan
→ intel contoh → aturan deteksi → deteksi (Sigma/IoC/ELANG-1) → korelasi insiden →
playbook SOAR. Setiap langkah idempoten kecuali simulator; simulator dilewati bila
event sudah ada (agar tak menggandakan baseline).

Playbook dijalankan sekali per insiden lewat `app.soar` (Matriks Otonomi menentukan
auto vs approval — §A.5 no.1–2), sehingga dashboard langsung berisi aksi otomatis
**dan** approval yang menunggu Commander.

`--reset` menolak berjalan di ENVIRONMENT=prod. Reset menghapus database demo
seluruhnya (termasuk audit) — ini mengganti lingkungan, bukan mengubah entri audit.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine


def _step(msg: str) -> None:
    print(f"- {msg}", flush=True)


def populate(session_factory=SessionLocal, bind=engine) -> dict:
    import app.models  # noqa: F401  registrasi model
    from app.correlation import correlate
    from app.detection import run_detection, seed_rules
    from app.intel.samples import seed_intel
    from app.models.event import Event
    from app.models.incident import Incident
    from app.models.soar import PlaybookRun
    from app.seed import seed_users
    from app.simulator import run_all_scenarios, seed_assets
    from app.simulator.baseline import DEFAULT_BASELINE_DAYS, generate_baseline
    from app.soar import run_playbook, seed_playbooks

    Base.metadata.create_all(bind=bind)
    db = session_factory()
    summary: dict = {}
    try:
        _step("User demo per role")
        summary["users_created"] = seed_users(db)
        _step("Aset (K1/K2/K3)")
        seed_assets(db)

        if db.execute(select(func.count(Event.id))).scalar_one() == 0:
            _step(f"Baseline {DEFAULT_BASELINE_DAYS} hari + skenario serangan (bisa ~10-30 detik)")
            generate_baseline(db, days=DEFAULT_BASELINE_DAYS)
            for r in run_all_scenarios(db):
                print(f"    {r.name} ({r.technique}) -> {r.target}: {r.count} event")
        else:
            _step("Event sudah ada - simulator dilewati")

        _step("Threat intel contoh")
        seed_intel(db)
        _step("Aturan deteksi")
        seed_rules(db)
        _step("Deteksi (aturan + IoC + ELANG-1)")
        summary["detection"] = run_detection(db)
        _step("Korelasi alert -> insiden")
        summary["correlation"] = correlate(db)
        _step("Playbook SOAR (Matriks Otonomi)")
        seed_playbooks(db)

        ran = 0
        for inc in db.execute(select(Incident).order_by(Incident.id)).scalars().all():
            already = db.execute(
                select(func.count(PlaybookRun.id)).where(PlaybookRun.incident_id == inc.id)
            ).scalar_one()
            if already:
                continue
            try:
                run = run_playbook(db, incident_id=inc.id, actor="demo-seed")
            except ValueError:  # tak ada playbook yang cocok untuk teknik insiden ini
                continue
            ran += 1
            print(f"    {inc.incident_code} {inc.host} -> {run.playbook_code}: {run.status}")
        summary["playbook_runs"] = ran
    finally:
        db.close()
    return summary


def reset(bind=engine) -> None:
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="app.demo", description="Isi data demo PN-X")
    parser.add_argument("--reset", action="store_true", help="hapus semua data lalu isi ulang")
    args = parser.parse_args(argv)

    if args.reset:
        if get_settings().is_prod:
            print("Ditolak: --reset tidak boleh di ENVIRONMENT=prod.")
            sys.exit(2)
        _step("Reset database demo")
        reset()

    populate()
    print("\nSelesai. Login di http://localhost:5173 (password semua akun: ChangeMe123!)")


if __name__ == "__main__":
    main()
