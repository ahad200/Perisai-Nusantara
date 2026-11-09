"""Adapter eksekusi respons — **semua mock** (PRD §A.5 no.8: hanya mencatat aksi).

Antarmuka standar (FR-305): `execute(action, params)` dan `rollback(action, params,
prior)`. Di prototipe tak ada efek nyata; adapter hanya mengembalikan hasil
tersimulasi + mencatat ke log in-memory. Agen LLM TIDAK memanggil ini langsung —
hanya mesin SOAR (§A.5 no.1).

`ACTION_CATALOG` mendefinisikan sifat tiap aksi:
- `disruptive`  : mengganggu layanan (mempengaruhi keputusan Matriks Otonomi).
- `reversible`  : punya operasi rollback (FR-304).
Aksi non-disruptif (blok IoC perimeter, watchlist, forensik, naikkan logging) —
lihat footnote Matriks Otonomi §7.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActionSpec:
    action: str
    disruptive: bool
    reversible: bool
    label: str
    rollback_label: str


ACTION_CATALOG: dict[str, ActionSpec] = {
    "isolate_host": ActionSpec("isolate_host", True, True, "Isolasi host dari jaringan", "Lepas isolasi host"),
    "revoke_token": ActionSpec("revoke_token", True, True, "Cabut token/sesi akun", "Terbitkan ulang token"),
    "disable_account": ActionSpec("disable_account", True, True, "Nonaktifkan akun", "Aktifkan kembali akun"),
    "block_ip": ActionSpec("block_ip", False, True, "Blokir IP/IoC di perimeter", "Cabut blokir IP/IoC"),
    "add_watchlist": ActionSpec("add_watchlist", False, True, "Tambah ke watchlist", "Hapus dari watchlist"),
    "collect_forensics": ActionSpec("collect_forensics", False, False, "Kumpulkan artefak forensik", ""),
    "raise_logging": ActionSpec("raise_logging", False, True, "Naikkan level logging", "Kembalikan level logging"),
}

# Log aksi mock (untuk inspeksi/uji). Reset lewat `reset_log()`.
ACTION_LOG: list[dict] = []


def reset_log() -> None:
    ACTION_LOG.clear()


def spec_for(action: str) -> ActionSpec:
    spec = ACTION_CATALOG.get(action)
    if spec is None:
        # Aksi tak dikenal: perlakukan paling ketat (disruptif, tak reversibel).
        return ActionSpec(action, True, False, action, "")
    return spec


class MockAdapter:
    """Satu-satunya implementasi adapter di prototipe: mencatat, tak beraksi nyata."""

    name = "mock"

    def execute(self, action: str, params: dict) -> dict:
        spec = spec_for(action)
        entry = {"op": "execute", "action": action, "params": params, "adapter": self.name, "mock": True}
        ACTION_LOG.append(entry)
        return {
            "ok": True, "mock": True, "action": action, "label": spec.label,
            "params": params, "message": f"[MOCK] {spec.label} — {params or '(tanpa parameter)'}",
        }

    def rollback(self, action: str, params: dict, prior: dict | None) -> dict:
        spec = spec_for(action)
        entry = {"op": "rollback", "action": action, "params": params, "adapter": self.name, "mock": True}
        ACTION_LOG.append(entry)
        return {
            "ok": True, "mock": True, "action": action, "label": spec.rollback_label or f"rollback {action}",
            "params": params, "message": f"[MOCK] {spec.rollback_label or 'rollback'} — {params or '(tanpa parameter)'}",
        }


_ADAPTER = MockAdapter()


def get_adapter(action: str) -> MockAdapter:
    """Pilih adapter untuk aksi. Di prototipe selalu MockAdapter (FR-305 antarmuka standar)."""
    return _ADAPTER
