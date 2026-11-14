"""CLI simulator PN-X (data simulasi).

Contoh:
    python -m app.simulator all                # tanam aset + baseline + semua serangan
    python -m app.simulator seed-assets
    python -m app.simulator baseline --days 14
    python -m app.simulator attack bruteforce
    python -m app.simulator attack all
    python -m app.simulator attack bruteforce --target app-logistik-01
    python -m app.simulator attack ransomware --target ws-staff-05 --target cmd-core-01
    python -m app.simulator targets            # daftar hostname yang bisa jadi target
"""
from __future__ import annotations

import argparse
import sys

from app.core.database import Base, SessionLocal, engine
from app.simulator.baseline import DEFAULT_BASELINE_DAYS, generate_baseline
from app.simulator.fleet import seed_assets
from app.simulator.scenarios import SCENARIOS, fleet_hostnames, run_all_scenarios


def _ensure_tables() -> None:
    import app.models  # noqa: F401  registrasi model

    Base.metadata.create_all(bind=engine)


def _cmd_seed_assets(db) -> None:
    created = seed_assets(db)
    print(f"Aset dibuat: {len(created)} ({', '.join(created) or 'tidak ada baru'})")


def _cmd_baseline(db, days: int) -> None:
    print(f"Membuat baseline {days} hari… (bisa beberapa detik)")
    n = generate_baseline(db, days=days)
    print(f"Baseline selesai: {n} event tersimpan.")


def _cmd_attack(db, which: str, targets: list[str] | None = None) -> None:
    if which == "all":
        if targets:
            print("--target tidak berlaku untuk 'attack all'. Jalankan per skenario.")
            sys.exit(2)
        for r in run_all_scenarios(db):
            print(f"  {r.name} ({r.technique}) -> {r.target}: {r.count} event")
        return
    fn = SCENARIOS.get(which)
    if fn is None:
        print(f"Skenario tak dikenal: {which}. Pilihan: {', '.join(SCENARIOS)}, all")
        sys.exit(2)
    unknown = [t for t in targets or [] if t not in fleet_hostnames()]
    if unknown:
        print(f"Target tak dikenal: {', '.join(unknown)}. Pilihan: {', '.join(fleet_hostnames())}")
        sys.exit(2)
    for t in dict.fromkeys(targets or [None]):
        r = fn(db, target=t) if t else fn(db)
        print(f"{r.name} ({r.technique}) -> {r.target}: {r.count} event")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="app.simulator", description="Simulator log & serangan PN-X")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seed-assets", help="tanam armada aset contoh")
    p_base = sub.add_parser("baseline", help="generator baseline historis")
    p_base.add_argument("--days", type=int, default=DEFAULT_BASELINE_DAYS)
    p_atk = sub.add_parser("attack", help="jalankan skenario serangan")
    p_atk.add_argument("which", choices=[*SCENARIOS, "all"])
    p_atk.add_argument("--target", action="append", metavar="HOSTNAME",
                       help="host target (ulangi untuk beberapa host serentak)")
    sub.add_parser("targets", help="daftar hostname target beserta kritikalitas")
    sub.add_parser("all", help="seed-assets + baseline + attack all")

    args = parser.parse_args(argv)
    if args.cmd == "targets":
        from app.simulator.fleet import FLEET
        for fa in FLEET:
            print(f"  {fa.hostname:<18} {fa.criticality.value}  ({fa.segment})")
        return
    _ensure_tables()
    db = SessionLocal()
    try:
        if args.cmd == "seed-assets":
            _cmd_seed_assets(db)
        elif args.cmd == "baseline":
            _cmd_baseline(db, args.days)
        elif args.cmd == "attack":
            _cmd_attack(db, args.which, args.target)
        elif args.cmd == "all":
            _cmd_seed_assets(db)
            _cmd_baseline(db, DEFAULT_BASELINE_DAYS)
            _cmd_attack(db, "all")
    finally:
        db.close()


if __name__ == "__main__":
    main()
